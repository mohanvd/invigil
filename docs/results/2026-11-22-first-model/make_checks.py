"""Train and check the first device-type and distance-band models.

Run from the repo root (needs the labelled sessions in data/raw/, which stay on the laptop):
    python docs/results/2026-11-22-first-model/make_checks.py

Writes next to this file:
    train_output.md          the standard ml.train report (5 grouped folds, whole sessions held out)
    confusion_type.csv, confusion_band.csv
    checks.txt               the extra checks the report quotes (other splits, feature subsets)
    rssi_by_distance.png     window RSSI by distance, one panel per device
and saves the two models, trained on every session, to ml/models/ (gitignored).

No hashed addresses are written: rows are grouped by device model and distance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut

sys.path.insert(0, ".")
from ml.features import BLE_COLS, FEATURE_COLS, MFR_COLS, SPECTRUM_COLS, dataset  # noqa: E402
from ml.train import evaluate, make_model, report_md  # noqa: E402

RAW = Path("data/raw")
OUT = Path(__file__).resolve().parent
MODELS = Path("ml/models")

SUBSETS = {
    "all features": FEATURE_COLS,
    "BLE only (no spectrum)": BLE_COLS + MFR_COLS,
    "spectrum only": SPECTRUM_COLS,
}

# Brand tokens (docs/brand/tokens.json, light theme).
INK, INK_MUTED, LINE, PAPER = "#0E1726", "#4B5871", "#D3DAE4", "#FFFFFF"
BAND_COLORS = {"near": "#1F6FEB", "mid": "#D97706", "far": "#6B7280"}


def load() -> pd.DataFrame:
    df = dataset(RAW)
    info = {}
    for s in df["session"].unique():
        meta = json.loads((RAW / s / "session.json").read_text(encoding="utf-8"))
        dev = next(iter(meta["devices"].values()))
        info[s] = (dev["model"], float(dev["distance_m"]))
    df["device"] = df["session"].map(lambda s: info[s][0])
    df["dist"] = df["session"].map(lambda s: info[s][1])
    return df


def cv_predict(df: pd.DataFrame, target: str, cols: list[str], group: str) -> tuple[np.ndarray, np.ndarray]:
    """Leave one group out: each session (or device) is predicted by a model that never saw it."""
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

    w("== Band, three classes ==")
    for name, cols in SUBSETS.items():
        for group, label in (("session", "leave one session out"), ("device", "leave one device out")):
            y, p = cv_predict(df, "band", cols, group)
            w(f"{name:24s} {label:22s} {score(y, p)}")
    w("")

    core = df[df["dist"].isin([0.5, 1.5, 2.5, 3.0, 3.5])]
    w("== Band without the 1.0 m and 2.0 m sessions (they sit on band edges) ==")
    for name in ("all features", "BLE only (no spectrum)"):
        y, p = cv_predict(core, "band", SUBSETS[name], "session")
        w(f"{name}: {score(y, p)}")
        w(pd.crosstab(pd.Series(y, name="true"), pd.Series(p, name="predicted")).to_string())
        w("")

    mf = df[df["band"].isin(["mid", "far"])]
    w("== Mid vs far only (chance is 50% balanced) ==")
    for name in ("all features", "BLE only (no spectrum)"):
        for group, label in (("session", "leave one session out"), ("device", "leave one device out")):
            y, p = cv_predict(mf, "band", SUBSETS[name], group)
            w(f"{name:24s} {label:22s} {score(y, p)}")
    w("")
    y, p = cv_predict(mf, "band", SUBSETS["BLE only (no spectrum)"], "session")
    w("Mid vs far, BLE only, leave one session out: windows predicted per session")
    w(pd.crosstab([mf["device"], mf["dist"]], pd.Series(p, index=mf.index, name="predicted")).to_string())
    w("")
    w("Mid vs far, BLE only, one model per device (leave one session out)")
    for dev, g in mf.groupby("device"):
        if g["band"].nunique() < 2:
            w(f"{dev}: only one band recorded, skipped")
            continue
        y, p = cv_predict(g, "band", SUBSETS["BLE only (no spectrum)"], "session")
        w(f"{dev}: {score(y, p)}  ({g['session'].nunique()} sessions)")
    w("")

    w("== Spectrum by session, in recording order ==")
    w("The nRF24 sees the whole room. If these move with the clock and not with distance,")
    w("the spectrum features describe the room's Wi-Fi traffic, not the test device.")
    first = df.groupby("session")["t_start"].min().sort_values()
    s = df.groupby("session")[["spec_active", "spec_mean_frac", "rssi_median"]].median().loc[first.index]
    s.insert(0, "minute", ((first - first.iloc[0]) / 60000).round().astype(int).to_numpy())
    s.insert(1, "device", [df.loc[df["session"] == x, "device"].iat[0] for x in s.index])
    s.insert(2, "dist", [df.loc[df["session"] == x, "dist"].iat[0] for x in s.index])
    w(s.reset_index(drop=True).to_string(float_format=lambda v: f"{v:.3f}"))
    w("")

    w("== Type (phone vs earpiece) ==")
    type_subsets = {
        "all features": FEATURE_COLS,
        "no manufacturer columns": BLE_COLS + SPECTRUM_COLS,
        "BLE timing and RSSI only": BLE_COLS,
    }
    for name, cols in type_subsets.items():
        y, p = cv_predict(df, "type", cols, "session")
        w(f"{name:26s} leave one session out  {score(y, p)}")
    w("Leave one device out is not possible for type: there is only one earpiece.")
    return "\n".join(out) + "\n"


def plot(df: pd.DataFrame) -> None:
    devices = sorted(df["device"].unique())
    fig, axes = plt.subplots(1, len(devices), figsize=(3.2 * len(devices), 3.6), sharey=True)
    fig.patch.set_facecolor(PAPER)
    for ax, dev in zip(axes, devices):
        g = df[df["device"] == dev]
        dists = sorted(g["dist"].unique())
        data = [g.loc[g["dist"] == d, "rssi_median"] for d in dists]
        parts = ax.boxplot(data, positions=range(len(dists)), widths=0.6, patch_artist=True, showfliers=False)
        for box, d in zip(parts["boxes"], dists):
            band = g.loc[g["dist"] == d, "band"].iat[0]
            box.set(facecolor=BAND_COLORS[band], edgecolor=INK, alpha=0.85)
        for med in parts["medians"]:
            med.set(color=INK)
        ax.set_xticks(range(len(dists)), [f"{d:g}" for d in dists])
        ax.set_title(dev, color=INK, fontsize=10)
        ax.set_xlabel("distance (m)", color=INK_MUTED)
        ax.grid(axis="y", color=LINE)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("median RSSI per 5 s window (dBm)", color=INK_MUTED)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in BAND_COLORS.values()]
    fig.legend(handles, BAND_COLORS, loc="upper right", frameon=False, ncol=3)
    fig.suptitle("Window RSSI by distance: mid and far overlap", x=0.01, ha="left", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT / "rssi_by_distance.png", dpi=150)


def main() -> None:
    df = load()
    results = [evaluate(df, t) for t in ("type", "band")]
    (OUT / "train_output.md").write_text(report_md(results, RAW), encoding="utf-8")
    MODELS.mkdir(parents=True, exist_ok=True)
    for r in results:
        pd.DataFrame(r["confusion"], index=r["labels"], columns=r["labels"]).to_csv(OUT / f"confusion_{r['target']}.csv")
        joblib.dump(
            {"model": r["model"], "features": FEATURE_COLS, "classes": r["labels"]},
            MODELS / f"{r['target']}.joblib",
        )
        print(f"{r['target']}: unseen sessions {r['test_acc']:.1%}, training data {r['train_acc']:.1%}")
    (OUT / "checks.txt").write_text(checks(df), encoding="utf-8")
    plot(df)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
