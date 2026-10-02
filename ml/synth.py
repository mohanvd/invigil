"""Write fake labeled sessions so the training pipeline can be tested end to end.

Run from the repo root:
    python -m ml.synth --out data/synthetic
    python -m ml.train --data data/synthetic --name pipeline-check

The numbers below are guesses, not measurements. A score on this data proves
the code runs, nothing more. Never report it as Invigil's accuracy.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from server import contract
from server.logger import COLUMNS

START_TS = 1_790_000_000_000
SALT = "synthetic-sessions"

# type: (company ID, advertising interval ms, streams audio)
PROFILES = {
    "phone": ("0x004C", 300, False),
    "earpiece": ("0x004C", 120, True),
    "smartwatch": ("0x0087", 900, False),
    "allowed": ("0x0075", 300, False),
}
BAND_RSSI = {"near": -55, "mid": -64, "far": -72}  # median RSSI per band, dBm
RSSI_NOISE = 5.0
CATCH_RATE = 0.6  # share of advertisements the unit actually hears
SPECTRUM_EVERY_MS = 500
SWEEPS = 50
WIFI = range(27, 48)


def fake_addr(rng: random.Random) -> str:
    return contract.hash_addr(bytes(rng.randrange(256) for _ in range(6)), SALT)


def write_session(out: Path, name: str, dtype: str, band: str, seconds: int, rng: random.Random) -> Path:
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    mfr, interval, streams = PROFILES[dtype]
    interval = interval * rng.uniform(0.8, 1.2)
    target = fake_addr(rng)
    background = [(fake_addr(rng), rng.choice([None, "0x004C", "0x0006"]), rng.uniform(-90, -78)) for _ in range(2)]
    end = START_TS + seconds * 1000
    ble_rows = []

    def advertise(addr, mfr_id, base_rssi, every_ms):
        t = START_TS + rng.uniform(0, every_ms)
        while t < end:
            if rng.random() < CATCH_RATE:
                rssi = max(-127, min(0, round(rng.gauss(base_rssi, RSSI_NOISE))))
                msg = {"ts": int(t), "node": "N1", "addr": addr, "rssi": rssi, "mfr": mfr_id}
                contract.validate("ble", msg)
                ble_rows.append([int(t) + 30, msg["ts"], "N1", addr, rssi, mfr_id or ""])
            t += every_ms + rng.uniform(0, 10)  # BLE adds 0-10 ms of random delay

    advertise(target, mfr, BAND_RSSI[band] + rng.uniform(-3, 3), interval)
    for addr, mfr_id, rssi in background:
        advertise(addr, mfr_id, rssi, rng.choice([200, 1000]))
    ble_rows.sort(key=lambda r: r[1])

    spec_rows = []
    hop_busy = {"near": 0.06, "mid": 0.04, "far": 0.02}[band] if streams else 0.0
    for ts in range(START_TS, end, SPECTRUM_EVERY_MS):
        hits = []
        for ch in range(contract.NUM_CHANNELS):
            p = 0.002 + (0.25 if ch in WIFI else 0) + (hop_busy if 2 <= ch <= 80 else 0)
            hits.append(sum(rng.random() < p for _ in range(SWEEPS)))
        contract.validate("spectrum", {"ts": ts, "node": "N1", "sweeps": SWEEPS, "hits": hits})
        spec_rows.append([ts + 30, ts, "N1", SWEEPS, *hits])

    for kind, rows in (("ble", ble_rows), ("spectrum", spec_rows)):
        with open(folder / f"{kind}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS[kind])
            w.writerows(rows)
    meta = {"name": name, "synthetic": True, "devices": {target: {"type": dtype, "band": band}}}
    (folder / "session.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return folder


def generate(out: Path, repeats: int = 3, seconds: int = 60, seed: int = 0) -> list[Path]:
    rng = random.Random(seed)
    return [
        write_session(out, f"synthetic-{t}-{b}-{i}", t, b, seconds, rng)
        for t in PROFILES
        for b in BAND_RSSI
        for i in range(1, repeats + 1)
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write fake labeled sessions for pipeline tests.")
    parser.add_argument("--out", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--repeats", type=int, default=3, help="sessions per type and band")
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args(argv)
    sessions = generate(args.out, args.repeats, args.seconds)
    print(f"wrote {len(sessions)} fake sessions to {args.out}")


if __name__ == "__main__":
    main()
