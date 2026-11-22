"""Summary table and poster graph for the 2026-11-22 calibration sessions.

Run from the repo root (needs the raw sessions in data/raw/, which stay on the laptop):
    python docs/results/2026-11-22-calibration/make_summary.py

Writes summary.csv, baseline.txt and rssi_vs_distance.png next to this file.
No hashed addresses are written: each row is one device at one distance.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, ".")
from ml.features import CHANNEL_COLS, load_ble, load_spectrum  # noqa: E402

RAW = Path("data/raw")
OUT = Path(__file__).resolve().parent
CAIRO = timezone(timedelta(hours=2))

# model label in session.json -> name on the graph
DEVICES = {
    "phone B": "Phone B (iPhone)",
    "phone B class": "Phone B class (iPhone)",
    "phone C class": "Phone C class (Android, +1 dBm, 100 ms)",
    "earpiece B class": "Earpiece B class (Oraimo, case open)",
}
BASELINE = ("2026-11-22-live-113837", (11, 45), (11, 48))

# Brand tokens (docs/brand/tokens.json, light theme).
INK, INK_MUTED, LINE, PAPER = "#0E1726", "#4B5871", "#D3DAE4", "#FFFFFF"
SOFT = {"near": "#FBE2E3", "mid": "#FBEED3", "far": "#E2EBFA"}
BAND_INK = {"near": "#CC2F3B", "mid": "#B87400", "far": "#2563C9"}
BAND_EDGES = {"near": (0.0, 1.0), "mid": (1.0, 2.0), "far": (2.0, 3.75)}
STYLE = {
    "phone B": dict(color="#15243F", marker="o", ls="-"),
    "phone B class": dict(color="#0B7A68", marker="s", ls="-"),
    "phone C class": dict(color="#75839A", marker="^", ls="--"),
    "earpiece B class": dict(color="#6B3FA0", marker="D", ls="-."),
}


def calibration_rows() -> pd.DataFrame:
    rows = []
    for d in sorted(RAW.glob("2026-11-22-calib-*")):
        if "incomplete" in d.name or not (d / "session.json").exists():
            continue
        meta = json.loads((d / "session.json").read_text(encoding="utf-8"))
        ble = load_ble(d)
        secs = (ble["ts"].max() - ble["ts"].min()) / 1000
        for addr, lab in meta["devices"].items():
            if lab.get("model") not in DEVICES:
                continue
            t = ble[ble["addr"] == addr]
            rows.append(
                {
                    "device": lab["model"],
                    "type": lab["type"],
                    "state": lab.get("state", ""),
                    "distance_m": lab["distance_m"],
                    "band": lab["band"],
                    "session_s": round(secs),
                    "readings": len(t),
                    "readings_per_s": round(len(t) / secs, 2),
                    "rssi_median": t["rssi"].median(),
                    "rssi_p25": t["rssi"].quantile(0.25),
                    "rssi_p75": t["rssi"].quantile(0.75),
                    "rssi_max": t["rssi"].max(),
                    "mfr": t["mfr"].mode().iat[0] or "none",
                }
            )
    return pd.DataFrame(rows).sort_values(["device", "distance_m"]).reset_index(drop=True)


def baseline_summary() -> tuple[str, float]:
    name, (h0, m0), (h1, m1) = BASELINE
    start = int(datetime(2026, 11, 22, h0, m0, tzinfo=CAIRO).timestamp() * 1000)
    end = int(datetime(2026, 11, 22, h1, m1, tzinfo=CAIRO).timestamp() * 1000)
    ble, spec = load_ble(RAW / name), load_spectrum(RAW / name)
    ble = ble[(ble["ts"] >= start) & (ble["ts"] < end)]
    spec = spec[(spec["ts"] >= start) & (spec["ts"] < end)]
    per_dev = ble.groupby("addr").agg(n=("rssi", "size"), med=("rssi", "median"), mfr=("mfr", "first"))
    per_dev = per_dev.sort_values("med", ascending=False)
    frac = spec[CHANNEL_COLS].sum() / spec["sweeps"].sum()
    active = [int(c[2:]) for c in frac[frac >= 0.02].index]
    lines = [
        f"Baseline: {name}, 11:{m0:02d} to 11:{m1:02d} local time (UTC+2), empty room",
        f"BLE readings: {len(ble)} ({len(ble) / 180:.1f}/s), devices: {len(per_dev)}",
        f"Strongest device median: {per_dev['med'].max():.0f} dBm; devices with median above -80 dBm: {(per_dev['med'] > -80).sum()}",
        f"All readings: median {ble['rssi'].median():.0f} dBm, 99th percentile {ble['rssi'].quantile(0.99):.0f} dBm, max {ble['rssi'].max()} dBm",
        "Readings by manufacturer: "
        + ", ".join(f"{k or 'none'} {v}" for k, v in ble["mfr"].value_counts().items()),
        "Devices by median (no addresses): "
        + ", ".join(f"{r.med:.0f} dBm/{r.n} adv/{r.mfr or 'none'}" for r in per_dev.itertuples()),
        f"Spectrum messages: {len(spec)}, sweeps per message (median): {spec['sweeps'].median():.0f}",
        f"Channels active in >= 2% of sweeps: {active}",
    ]
    return "\n".join(lines) + "\n", float(per_dev["med"].max())


def plot(df: pd.DataFrame, baseline_top: float) -> None:
    plt.rcParams.update(
        {
            "font.family": ["IBM Plex Sans", "Segoe UI", "DejaVu Sans"],
            "font.size": 15,
            "axes.edgecolor": INK_MUTED,
            "axes.labelcolor": INK,
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
        }
    )
    fig, ax = plt.subplots(figsize=(12, 8.2), dpi=200)
    fig.patch.set_facecolor(PAPER)
    ymin, ymax = -104, -55
    for band, (x0, x1) in BAND_EDGES.items():
        ax.axvspan(x0, x1, color=SOFT[band], zorder=0, lw=0)
        ax.text((x0 + x1) / 2, ymax - 1.5, band.upper(), ha="center", va="top",
                fontsize=15, fontweight="bold", color=BAND_INK[band])
    ax.axhline(baseline_top, color=INK_MUTED, lw=1.5, ls=":", zorder=1)
    ax.text(3.72, baseline_top + 0.6, "strongest device in the empty room", ha="right",
            va="bottom", fontsize=12, color=INK_MUTED)
    for model, label in DEVICES.items():
        d = df[df["device"] == model]
        s = STYLE[model]
        ax.plot(d["distance_m"], d["rssi_median"], color=s["color"], ls=s["ls"], lw=2.5,
                marker=s["marker"], ms=9, label=label, zorder=3)
    ax.set_xlim(0, 3.75)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5])
    ax.set_xlabel("Distance from the unit (m)")
    ax.set_ylabel("Median RSSI over 60 s (dBm)")
    ax.grid(axis="y", color=LINE, lw=0.8, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, frameon=False, fontsize=13)
    ax.set_title("Signal strength vs distance, unit N1, 2026-11-22", loc="left",
                 fontsize=19, fontweight="bold", color=INK, pad=14)
    fig.text(0.01, 0.01, "Smartwatch (Huawei, connected to its phone) was not heard at 0.5 m and is not shown. "
             "Phone B class was not heard at 2 m.", fontsize=11, color=INK_MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "rssi_vs_distance.png", facecolor=PAPER)


def main() -> None:
    df = calibration_rows()
    df.to_csv(OUT / "summary.csv", index=False)
    text, top = baseline_summary()
    (OUT / "baseline.txt").write_text(text, encoding="utf-8")
    plot(df, top)
    print(df.to_string(index=False))
    print(text)


if __name__ == "__main__":
    main()
