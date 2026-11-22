"""Train and check model v2: device type and near / not near.

Run from the repo root (needs the labelled sessions in data/raw/, which stay on the laptop):
    python docs/results/2026-11-23-model-v2/make_checks.py

Writes next to this file:
    train_output.md          the standard ml.train report (5 grouped folds, whole sessions held out)
    confusion_type.csv, confusion_band.csv
    checks.txt               the extra checks the report quotes
    response_time.csv        the replay of each session through server/detector.py
and saves both models, trained on every session, to ml/models/ (gitignored),
where server/detector.py loads them.

No hashed addresses are written: rows are grouped by device model and distance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut

sys.path.insert(0, ".")
from ml.features import BAND_FEATURE_COLS, BLE_COLS, FEATURE_COLS, MFR_COLS, dataset, load_ble, load_spectrum  # noqa: E402
from ml.train import TARGET_FEATURES, evaluate, make_model, report_md  # noqa: E402
from server.config import DEFAULT_MIN_RSSI  # noqa: E402
from server.detector import BATCH_WAIT_S, MIN_GAP_S, STEP_S, Detector  # noqa: E402

RAW = Path("data/raw")
OUT = Path(__file__).resolve().parent
MODELS = Path("ml/models")
REPLAY_S = 30  # how long after the first reading to keep looking for a detection


def load() -> tuple[pd.DataFrame, dict]:
    df = dataset(RAW)
    info = {}
    for s in df["session"].unique():
        meta = json.loads((RAW / s / "session.json").read_text(encoding="utf-8"))
        addr, dev = next(iter(meta["devices"].items()))
        info[s] = {"addr": addr, "device": dev["model"], "dist": float(dev["distance_m"]), "type": dev["type"]}
    df["device"] = df["session"].map(lambda s: info[s]["device"])
    df["dist"] = df["session"].map(lambda s: info[s]["dist"])
    return df, info


def cv_predict(df, target, cols, group):
    X, y, g = df[cols].to_numpy(dtype=float), df[target].to_numpy(), df[group]
    pred = np.empty(len(y), dtype=object)
    for tr, te in LeaveOneGroupOut().split(X, y, g):
        assert not set(g.iloc[tr]) & set(g.iloc[te])
        pred[te] = make_model().fit(X[tr], y[tr]).predict(X[te])
    return y, pred


def score(y, pred) -> str:
    return f"accuracy {accuracy_score(y, pred):6.1%}   balanced {balanced_accuracy_score(y, pred):6.1%}"


def checks(df: pd.DataFrame) -> str:
    out = []
    w = out.append
    w("Windows per device and distance (5 s windows, 1 s step)")
    w(df.groupby(["device", "dist"]).size().unstack(fill_value=0).to_string())
    w("")

    w("== Near / not near, RSSI features only (the model used) ==")
    share = (df["band"] == "not_near").mean()
    w(f"A model that always says not_near scores {share:.1%} accuracy (balanced 50.0%).")
    for group, label in (("session", "leave one session out"), ("device", "leave one device out")):
        y, p = cv_predict(df, "band", BAND_FEATURE_COLS, group)
        near = y == "near"
        w(f"{label:22s} {score(y, p)}   near found {np.mean(p[near] == 'near'):5.1%}"
          f"   not_near called near {np.mean(p[~near] == 'near'):5.1%}")
        w(pd.crosstab(pd.Series(y, name="true"), pd.Series(p, name="predicted")).to_string())
        if group == "session":
            loso = p
    w("")
    w("Share of windows called near, per device and distance (leave one session out)")
    called = pd.Series(loso == "near", index=df.index)
    w(called.groupby([df["device"], df["dist"]]).mean().unstack().map(lambda v: f"{v:.0%}").to_string())
    w("")
    edge = ~df["dist"].isin([1.0])
    y, p = cv_predict(df[edge], "band", BAND_FEATURE_COLS, "session")
    w(f"Without the 1.0 m sessions (on the edge): {score(y, p)}")
    w(pd.crosstab(pd.Series(y, name="true"), pd.Series(p, name="predicted")).to_string())
    w("")

    w("== Near / not near with other feature sets, leave one session out ==")
    for name, cols in (("BLE timing and RSSI", BLE_COLS), ("BLE and manufacturer", BLE_COLS + MFR_COLS)):
        y, p = cv_predict(df, "band", cols, "session")
        near = y == "near"
        w(f"{name:22s} {score(y, p)}   near found {np.mean(p[near] == 'near'):5.1%}")
    w("")

    w("== Type (phone vs earpiece), leave one session out ==")
    for name, cols in (
        ("all features (the model used)", FEATURE_COLS),
        ("BLE only, no spectrum", BLE_COLS + MFR_COLS),
        ("BLE timing and RSSI only", BLE_COLS),
    ):
        y, p = cv_predict(df, "type", cols, "session")
        w(f"{name:30s} {score(y, p)}")
    w("Leave one device out is not possible for type: there is only one earpiece.")
    return "\n".join(out) + "\n"


def decision_times(ble_rx: list[int], start: int, end: int) -> list[int]:
    """When the live detector would decide, given the arrival times of ble messages."""
    wait, gap, step = int(BATCH_WAIT_S * 1000), int(MIN_GAP_S * 1000), int(STEP_S * 1000)
    arrivals = sorted(t for t in ble_rx if start <= t <= end)
    times, last, j = [], start, 0
    t = start
    while t <= end:
        nxt = arrivals[j] + wait if j < len(arrivals) else None
        if nxt is not None and nxt <= last + step:
            j += 1
            if nxt - last >= gap:
                times.append(nxt)
                last = nxt
            continue
        last += step  # no batch for a second: decide anyway
        times.append(last)
        t = last
    return times


def replay(df: pd.DataFrame, info: dict) -> pd.DataFrame:
    """Feed each session to the detector in the order its messages reached the laptop.

    Every session is replayed with models trained on the other 23, so the
    answers are held out. The detector decides when it does live: 50 ms after
    each ble message arrives (no closer than 0.5 s apart), and at least once a
    second. Times are on the laptop clock, from the recorded arrival times.
    """
    rows = []
    for session, meta in info.items():
        train = df[df["session"] != session]
        models = {}
        for target in ("type", "band"):
            cols = TARGET_FEATURES[target]
            model = make_model().fit(train[cols].to_numpy(dtype=float), train[target].to_numpy())
            models[target] = {"model": model, "features": cols}
        det = Detector(models, min_rssi=DEFAULT_MIN_RSSI)

        ble = load_ble(RAW / session)
        spec = load_spectrum(RAW / session)
        mine = ble[ble["addr"] == meta["addr"]]
        first_ts = int(mine["ts"].min())
        first_rx = int(mine.loc[mine["ts"].idxmin(), "rx_ts"])
        start = int(min(ble["rx_ts"].min(), spec["rx_ts"].min() if not spec.empty else np.inf))
        # Messages in arrival order: (rx_ts, kind, payload)
        events = [(int(r.rx_ts), "ble", {"node": r.node, "ts": int(r.ts), "readings": [
            {"ts": int(r.ts), "addr": r.addr, "rssi": int(r.rssi), "mfr": r.mfr or None}]}) for r in ble.itertuples()]
        chan = [c for c in spec.columns if c.startswith("ch")]
        events += [(int(r["rx_ts"]), "spectrum", {"node": r["node"], "ts": int(r["ts"]), "sweeps": int(r["sweeps"]),
                    "hits": [int(r[c]) for c in chan]}) for _, r in spec.iterrows()]
        events.sort(key=lambda e: e[0])

        expected_band = "near" if meta["dist"] < 1.0 else "not_near"
        found = {"any": None, "type": None, "both": None}
        ticks = decision_times([e[0] for e in events if e[1] == "ble"], start, first_rx + REPLAY_S * 1000)
        i = 0
        for tick in ticks:
            if None not in found.values():
                break
            while i < len(events) and events[i][0] <= tick:
                det.add(events[i][1], events[i][2])
                i += 1
            for d in det.decide(tick):
                if d["addr"] != meta["addr"]:
                    continue
                found["any"] = found["any"] or tick
                if d["type"] == meta["type"]:
                    found["type"] = found["type"] or tick
                    if d["band"] == expected_band:
                        found["both"] = found["both"] or tick

        def secs(t):
            return None if t is None else round((t - first_ts) / 1000, 1)

        rows.append({
            "device": meta["device"], "distance_m": meta["dist"],
            "first_heard_to_laptop_s": round((first_rx - first_ts) / 1000, 2),
            "first_alert_s": secs(found["any"]),
            "first_right_type_s": secs(found["type"]),
            "first_right_type_and_band_s": secs(found["both"]),
        })
    return pd.DataFrame(rows).sort_values(["device", "distance_m"]).reset_index(drop=True)


def main() -> None:
    df, info = load()
    results = [evaluate(df, t) for t in ("type", "band")]
    (OUT / "train_output.md").write_text(report_md(results, RAW), encoding="utf-8")
    MODELS.mkdir(parents=True, exist_ok=True)
    for r in results:
        pd.DataFrame(r["confusion"], index=r["labels"], columns=r["labels"]).to_csv(OUT / f"confusion_{r['target']}.csv")
        joblib.dump(
            {"model": r["model"], "features": r["features"], "classes": list(r["model"].classes_)},
            MODELS / f"{r['target']}.joblib",
        )
        print(f"{r['target']}: unseen sessions {r['test_acc']:.1%}, training data {r['train_acc']:.1%}")
    (OUT / "checks.txt").write_text(checks(df), encoding="utf-8")
    rt = replay(df, info)
    rt.to_csv(OUT / "response_time.csv", index=False)
    print(rt.to_string())
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
