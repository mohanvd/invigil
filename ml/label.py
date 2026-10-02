"""Help label a recorded session: list every address the unit heard.

Run from the repo root right after a recording:
    python -m ml.label data/raw/2026-10-20-earpiece-near-streaming-1

It prints every hashed address in the session, strongest first. The test
device is almost always the strongest one that does not also show up in the
empty-room baseline. If the folder has no session.json yet, it writes one with
the strongest address filled in and "?" as its labels. Replace the "?" values
(training refuses to run while any are left) and delete any wrong entries.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ml.features import BANDS, TYPES, load_ble


def summary(session_dir: Path):
    ble = load_ble(session_dir)
    if ble.empty:
        return ble
    g = ble.groupby("addr")
    out = g.agg(
        advs=("rssi", "size"),
        rssi_median=("rssi", "median"),
        rssi_max=("rssi", "max"),
        mfr=("mfr", lambda s: s.mode().iat[0] or "none"),
        first_s=("ts", "min"),
        last_s=("ts", "max"),
    )
    t0 = ble["ts"].min()
    out["first_s"] = ((out["first_s"] - t0) / 1000).round(1)
    out["last_s"] = ((out["last_s"] - t0) / 1000).round(1)
    return out.sort_values(["rssi_median", "advs"], ascending=False)


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SystemExit("usage: python -m ml.label <session folder>")
    session_dir = Path(args[0])
    table = summary(session_dir)
    if table.empty:
        raise SystemExit(f"no BLE readings in {session_dir}")
    print(table.to_string())

    path = session_dir / "session.json"
    if path.exists():
        print(f"\n{path} already exists, left unchanged.")
        return
    top = table.index[0]
    template = {
        "name": session_dir.name,
        "notes": "",
        "devices": {top: {"type": "?", "band": "?", "model": "", "state": "", "position": ""}},
    }
    path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {path} with {top} as the test device.")
    print(f"Set type to one of {', '.join(TYPES)} and band to one of {', '.join(BANDS)}.")


if __name__ == "__main__":
    main()
