"""Turn one recorded session into feature rows: one row per device per time window.

A session is a folder written by the logger (data/raw/<date>-<name>/) with
ble.csv and spectrum.csv, plus a session.json you write by hand that says which
hashed addresses are test devices and what their labels are. See
docs/data-protocol.md.

Each row describes one device over WINDOW_S seconds:
  - BLE features come from that device's own advertisements.
  - Spectrum features come from the nRF24 sweeps in the same window. They
    describe the whole room, not one device, so they are only fully trustworthy
    in sessions with one test device at a time.

Run from the repo root to inspect a session:
    python -m ml.features data/raw/2026-10-20-earpiece-near-streaming-1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from server import contract

# ---------------------------------------------------------------------------
# PLACEHOLDERS. Revisit after the first real recordings.
# ---------------------------------------------------------------------------

WINDOW_S = 5.0  # one decision covers 5 s of data, matching DR1 (response <= 5 s)
STEP_S = 1.0  # a new window starts every second
MIN_ADVS = 2  # a device needs at least this many advertisements in a window

# A channel counts as active in a window if it trips RPD in at least this share
# of sweeps. Set it from the empty-room baseline sessions.
ACTIVE_FRAC = 0.02

# Bluetooth SIG company IDs worth their own column. Everything else is "other".
# Check new ones against the Bluetooth SIG assigned numbers list.
KNOWN_MFR = {
    "0x004C": "apple",
    "0x0075": "samsung",
    "0x00E0": "google",
    "0x0006": "microsoft",
    "0x038F": "xiaomi",
    "0x027D": "huawei",
}

# ---------------------------------------------------------------------------

TYPES = ("phone", "earpiece", "smartwatch", "allowed")
BANNED = ("phone", "earpiece", "smartwatch")
BANDS = ("near", "mid", "far")

# BLE advertising channels 37, 38, 39 sit at 2402, 2426, 2480 MHz.
BLE_ADV_CHANNELS = (2, 26, 80)

MISSING = -1.0  # stands in for "could not be measured in this window"

CHANNEL_COLS = [f"ch{c:03d}" for c in range(contract.NUM_CHANNELS)]
MFR_COLS = [f"mfr_{name}" for name in KNOWN_MFR.values()] + ["mfr_other", "mfr_none"]
BLE_COLS = [
    "n_adv",
    "rssi_mean",
    "rssi_median",
    "rssi_std",
    "rssi_min",
    "rssi_max",
    "adv_interval_ms",
    "adv_interval_std_ms",
]
SPECTRUM_COLS = [
    "spec_sweeps",
    "spec_mean_frac",
    "spec_active",
    "spec_runs",
    "spec_longest_run",
    "spec_scattered",
    "spec_adv_frac",
]
FEATURE_COLS = BLE_COLS + MFR_COLS + SPECTRUM_COLS
META_COLS = ["session", "node", "addr", "t_start", "type", "band"]


class SessionError(ValueError):
    """A session folder or its session.json is missing or wrong."""


# --- loading ----------------------------------------------------------------


def load_meta(session_dir: Path) -> dict:
    """Read and check session.json. Returns {"name": ..., "devices": {addr: {...}}}."""
    path = Path(session_dir) / "session.json"
    if not path.exists():
        raise SessionError(f"{path} is missing. Run: python -m ml.label {session_dir}")
    meta = json.loads(path.read_text(encoding="utf-8"))
    devices = meta.get("devices")
    if not isinstance(devices, dict):
        raise SessionError(f"{path}: 'devices' must be an object of addr -> labels")
    for addr, info in devices.items():
        if not isinstance(addr, str) or len(addr) != 12:
            raise SessionError(f"{path}: {addr!r} is not a 12-char hashed address")
        if info.get("type") not in TYPES:
            raise SessionError(f"{path}: {addr} type must be one of {', '.join(TYPES)}")
        if info.get("band") not in BANDS:
            raise SessionError(f"{path}: {addr} band must be one of {', '.join(BANDS)}")
    meta.setdefault("name", Path(session_dir).name)
    return meta


def load_ble(session_dir: Path) -> pd.DataFrame:
    path = Path(session_dir) / "ble.csv"
    if not path.exists():
        return pd.DataFrame(columns=["rx_ts", "ts", "node", "addr", "rssi", "mfr"])
    # keep_default_na=False so an empty mfr cell stays "" instead of NaN.
    df = pd.read_csv(path, dtype={"addr": str, "mfr": str, "node": str}, keep_default_na=False)
    return df.sort_values("ts", kind="stable").reset_index(drop=True)


def load_spectrum(session_dir: Path) -> pd.DataFrame:
    path = Path(session_dir) / "spectrum.csv"
    if not path.exists():
        return pd.DataFrame(columns=["rx_ts", "ts", "node", "sweeps", *CHANNEL_COLS])
    df = pd.read_csv(path, dtype={"node": str})
    return df.sort_values("ts", kind="stable").reset_index(drop=True)


# --- feature math -----------------------------------------------------------


def ble_features(ts_ms: np.ndarray, rssi: np.ndarray, mfr: str) -> dict:
    """Features for one device in one window. ts_ms must be sorted."""
    out = {
        "n_adv": float(len(rssi)),
        "rssi_mean": float(np.mean(rssi)),
        "rssi_median": float(np.median(rssi)),
        "rssi_std": float(np.std(rssi)),
        "rssi_min": float(np.min(rssi)),
        "rssi_max": float(np.max(rssi)),
    }
    gaps = np.diff(ts_ms)
    gaps = gaps[gaps > 0]  # two reports in the same ms are one advertisement seen twice
    # The median gap survives missed packets better than the mean: a missed
    # advertisement makes one gap twice as long but barely moves the median.
    out["adv_interval_ms"] = float(np.median(gaps)) if len(gaps) else MISSING
    out["adv_interval_std_ms"] = float(np.std(gaps)) if len(gaps) > 1 else MISSING
    out.update(mfr_onehot(mfr))
    return out


def mfr_onehot(mfr: str | None) -> dict:
    out = dict.fromkeys(MFR_COLS, 0.0)
    if not mfr:
        out["mfr_none"] = 1.0
    elif mfr in KNOWN_MFR:
        out[f"mfr_{KNOWN_MFR[mfr]}"] = 1.0
    else:
        out["mfr_other"] = 1.0
    return out


def spectrum_features(spec: pd.DataFrame) -> dict:
    """Features for all nRF24 sweeps in one window.

    Wi-Fi shows up as one wide block of busy channels. Bluetooth audio hops
    over 79 channels, so it shows up as many short, scattered hits. The
    features below try to tell those two shapes apart.
    """
    if spec.empty:
        return dict.fromkeys(SPECTRUM_COLS, MISSING)
    sweeps = float(spec["sweeps"].sum())
    frac = spec[CHANNEL_COLS].to_numpy(dtype=float).sum(axis=0) / sweeps
    active = frac >= ACTIVE_FRAC
    runs = _runs(active)
    return {
        "spec_sweeps": sweeps,
        "spec_mean_frac": float(frac.mean()),
        "spec_active": float(active.sum()),
        "spec_runs": float(len(runs)),
        "spec_longest_run": float(max(runs, default=0)),
        "spec_scattered": float(sum(r for r in runs if r <= 2)),
        "spec_adv_frac": float(frac[list(BLE_ADV_CHANNELS)].mean()),
    }


def _runs(active: np.ndarray) -> list[int]:
    """Lengths of each block of consecutive active channels."""
    runs, n = [], 0
    for a in active:
        if a:
            n += 1
        elif n:
            runs.append(n)
            n = 0
    if n:
        runs.append(n)
    return runs


# --- whole session ----------------------------------------------------------


def session_features(session_dir: Path, labeled_only: bool = True) -> pd.DataFrame:
    """One row per (device, window) for a session.

    With labeled_only=True, only addresses listed in session.json are kept.
    Everything else in the room (other people's phones, the hall's own
    devices) is background and is dropped.
    """
    session_dir = Path(session_dir)
    meta = load_meta(session_dir) if labeled_only else {"name": session_dir.name, "devices": {}}
    devices = meta["devices"]
    ble = load_ble(session_dir)
    spec = load_spectrum(session_dir)
    if labeled_only:
        ble = ble[ble["addr"].isin(devices)]
    if ble.empty:
        return pd.DataFrame(columns=META_COLS + FEATURE_COLS)

    window_ms = int(WINDOW_S * 1000)
    step_ms = int(STEP_S * 1000)
    start, end = int(ble["ts"].min()), int(ble["ts"].max())
    spec_ts = spec["ts"].to_numpy() if not spec.empty else np.array([], dtype=np.int64)

    rows = []
    for t0 in range(start, max(start, end - window_ms) + 1, step_ms):
        t1 = t0 + window_ms
        in_win = ble[(ble["ts"] >= t0) & (ble["ts"] < t1)]
        if in_win.empty:
            continue
        lo, hi = np.searchsorted(spec_ts, [t0, t1])
        spec_feats = spectrum_features(spec.iloc[lo:hi])
        for (node, addr), g in in_win.groupby(["node", "addr"], sort=True):
            if len(g) < MIN_ADVS:
                continue
            mfr = g["mfr"].mode().iat[0] if "mfr" in g else ""
            labels = devices.get(addr, {})
            row = {
                "session": meta["name"],
                "node": node,
                "addr": addr,
                "t_start": t0,
                "type": labels.get("type"),
                "band": labels.get("band"),
            }
            row.update(ble_features(g["ts"].to_numpy(), g["rssi"].to_numpy(dtype=float), mfr))
            row.update(spec_feats)
            rows.append(row)

    return pd.DataFrame(rows, columns=META_COLS + FEATURE_COLS)


def find_sessions(base: Path) -> list[Path]:
    """Every folder under base that has a session.json."""
    return sorted(p.parent for p in Path(base).glob("*/session.json"))


def dataset(base: Path) -> pd.DataFrame:
    """Feature rows from every labeled session under base."""
    frames = [session_features(s) for s in find_sessions(base)]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=META_COLS + FEATURE_COLS)
    return pd.concat(frames, ignore_index=True)


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit("usage: python -m ml.features <session folder>")
    df = session_features(Path(args[0]))
    print(f"{len(df)} rows, {df['addr'].nunique()} labeled device(s)")
    if not df.empty:
        print(df.groupby(["addr", "type", "band"])[["n_adv", "rssi_median", "adv_interval_ms", "spec_scattered"]].median())


if __name__ == "__main__":
    main()
