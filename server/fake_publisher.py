"""Fake node publisher: three simulated nodes that follow the MQTT contract.

Use it to build and test the logger, dashboard, and ML pipeline before the
hardware is ready. Run from the repo root:
    python -m server.fake_publisher

The data has the right shape, not the right physics. Every number in the
PLACEHOLDERS section is a guess. Replace them with calibration results from
docs/results/ once the real nodes are running, and never train the final
models on fake data.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import secrets
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import paho.mqtt.client as mqtt

from server import contract
from server.config import load_config

log = logging.getLogger("invigil.fake")

FAKE_FW = "0.1.0-fake"  # shows up in status.csv, so fake runs are easy to spot

# ---------------------------------------------------------------------------
# PLACEHOLDERS. None of these are measured yet.
# ---------------------------------------------------------------------------

# Hall layout in metres: two rows of three seats, one node on each of three sides.
SEATS = {
    "S1": (0.8, 1.0), "S2": (2.0, 1.0), "S3": (3.2, 1.0),
    "S4": (0.8, 2.2), "S5": (2.0, 2.2), "S6": (3.2, 2.2),
}
NODE_POSITIONS = {"N1": (0.0, 0.0), "N2": (4.0, 0.0), "N3": (2.0, 3.2)}

PATH_LOSS_EXP = 2.2  # indoor log-distance exponent
PATH_LOSS_1M_DB = 40.0  # free-space loss at 1 m and 2.4 GHz
RSSI_NOISE_DB = 4.0  # packet-to-packet fading, standard deviation
BLE_SENSITIVITY_DBM = -92  # weakest advertisement a node still decodes
BLE_CATCH_RATE = 0.6  # share of in-range advertisements a node actually catches
RPD_THRESHOLD_DBM = -64  # nRF24L01 RPD trips above this (datasheet value)
BODY_LOSS_DB = 8.0  # extra loss for a device in an ear or a pocket
HOP_BUSY = 0.015  # chance a hop channel is in use at the instant it is sampled
NOISE_HIT_RATE = 0.002  # background RPD hits per channel per sweep
WIFI_CHANNELS = range(27, 48)  # Wi-Fi channel 6 (2427-2447 MHz) as nRF channels
WIFI_BUSY = 0.25  # airtime share of the hall Wi-Fi
BT_CLASSIC_CHANNELS = range(2, 81)  # the 79 Bluetooth Classic hop channels, 2402-2480 MHz

# ---------------------------------------------------------------------------


@dataclass
class Device:
    label: str  # ground truth, printed at start
    kind: str  # phone / earpiece / smartwatch / allowed
    addr: str  # hashed address, exactly as the firmware would send it
    mfr: str | None  # Bluetooth SIG company ID, or None if the ads carry none
    adv_interval_ms: int | None  # None means the device is not advertising
    rssi_1m: float  # BLE RSSI seen at 1 m, dBm
    audio_tx_dbm: float | None  # Bluetooth audio link power, None if not streaming
    where: Callable[[float], tuple[float, float]]  # seconds since epoch -> (x, y)
    adv_phase_ms: float = 0.0


def fixed(pos: tuple[float, float]) -> Callable[[float], tuple[float, float]]:
    return lambda t: pos


def patrol(points: list[tuple[float, float]], speed_mps: float) -> Callable[[float], tuple[float, float]]:
    """Walk a closed loop through the points at constant speed."""
    legs = [(a, b, math.dist(a, b)) for a, b in zip(points, points[1:] + points[:1])]
    loop_m = sum(length for _, _, length in legs)

    def where(t: float) -> tuple[float, float]:
        s = (t * speed_mps) % loop_m
        for a, b, length in legs:
            if s <= length:
                f = s / length
                return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
            s -= length
        return points[0]

    return where


def default_devices(salt: str, rng: random.Random) -> list[Device]:
    def addr() -> str:
        return contract.hash_addr(rng.randbytes(6), salt)

    devices = [
        Device("phone in a pocket, seat S2", "phone", addr(), "0x004C",
               adv_interval_ms=300, rssi_1m=-62, audio_tx_dbm=None, where=fixed(SEATS["S2"])),
        # Many earpieces stop advertising once connected, so this one is silent
        # on BLE and only the spectrum scan can see it. Verify with the real earpiece.
        Device("earpiece streaming audio, seat S5", "earpiece", addr(), "0x0075",
               adv_interval_ms=None, rssi_1m=-68, audio_tx_dbm=0.0, where=fixed(SEATS["S5"])),
        Device("smartwatch on a wrist, seat S4", "smartwatch", addr(), "0x00E0",
               adv_interval_ms=1000, rssi_1m=-64, audio_tx_dbm=None, where=fixed(SEATS["S4"])),
        Device("proctor phone, walking the room", "allowed", addr(), "0x0075",
               adv_interval_ms=500, rssi_1m=-59, audio_tx_dbm=None,
               where=patrol([(0.3, 0.4), (3.7, 0.4), (3.7, 2.8), (0.3, 2.8)], speed_mps=0.5)),
    ]
    for d in devices:
        if d.adv_interval_ms:
            d.adv_phase_ms = rng.uniform(0, d.adv_interval_ms)
    return devices


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(math.dist(a, b), 0.3)  # log-distance model breaks down very close in


def either(p: float, q: float) -> float:
    """Probability that at least one of two independent events happens."""
    return 1 - (1 - p) * (1 - q)


def spectrum_hits(here: tuple[float, float], t_ms: float, devices: list[Device],
                  sweeps: int, rng: random.Random) -> list[int]:
    p = [NOISE_HIT_RATE] * contract.NUM_CHANNELS
    # Wi-Fi: a fixed block of busy channels.
    for c in WIFI_CHANNELS:
        p[c] = either(p[c], WIFI_BUSY)
    # Bluetooth audio: scattered hits across the hop set. Adaptive frequency
    # hopping steers the link away from channels Wi-Fi is using.
    hop_set = [c for c in BT_CLASSIC_CHANNELS if c not in WIFI_CHANNELS]
    for dev in devices:
        if dev.audio_tx_dbm is None:
            continue
        loss = PATH_LOSS_1M_DB + 10 * PATH_LOSS_EXP * math.log10(distance(here, dev.where(t_ms / 1000)))
        rx_dbm = dev.audio_tx_dbm - BODY_LOSS_DB - loss
        above = 1 / (1 + math.exp(-(rx_dbm - RPD_THRESHOLD_DBM) / 3))  # soft threshold for fading
        for c in hop_set:
            p[c] = either(p[c], HOP_BUSY * above)
    return [sum(rng.random() < pc for _ in range(sweeps)) for pc in p]


def simulate_window(node: str, t0: int, t1: int, devices: list[Device],
                    sweeps: int, rng: random.Random) -> list[tuple[str, dict]]:
    """Messages one node sends after scanning from t0 to t1 (ms since epoch).

    BLE readings carry the time each advertisement was heard. The spectrum
    message covers the whole scan window and carries its end time.
    """
    here = NODE_POSITIONS[node]
    ble = []
    for dev in devices:
        if dev.adv_interval_ms is None:
            continue
        k = math.ceil((t0 - dev.adv_phase_ms) / dev.adv_interval_ms)
        while True:
            # BLE adds 0-10 ms of random delay to every advertising event.
            t = dev.adv_phase_ms + k * dev.adv_interval_ms + rng.uniform(0, 10)
            if t >= t1:
                break  # anything later falls in the send window and is dropped
            k += 1
            d = distance(here, dev.where(t / 1000))
            rssi = dev.rssi_1m - 10 * PATH_LOSS_EXP * math.log10(d) + rng.gauss(0, RSSI_NOISE_DB)
            if rssi < BLE_SENSITIVITY_DBM or rng.random() > BLE_CATCH_RATE:
                continue
            ble.append({"ts": int(t), "node": node, "addr": dev.addr,
                        "rssi": max(-127, min(0, round(rssi))), "mfr": dev.mfr})
    ble.sort(key=lambda m: m["ts"])
    msgs = [("ble", m) for m in ble]
    hits = spectrum_hits(here, (t0 + t1) / 2, devices, sweeps, rng)
    msgs.append(("spectrum", {"ts": t1, "node": node, "sweeps": sweeps, "hits": hits}))
    return msgs


@dataclass
class SimNode:
    node_id: str
    scan_start: int  # ms since epoch
    boot_ms: int
    next_status: int


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def run(send: Callable[[str, dict], None], devices: list[Device], scan_ms: int, send_ms: int,
        sweeps: int, duration_s: float, rng: random.Random, status_every_s: int = 10) -> None:
    """Drive the three nodes on alternating scan and send windows until time runs out."""
    cycle = scan_ms + send_ms
    start = now_ms()
    nodes = [
        # Nodes boot at different times, so their windows are not aligned.
        SimNode(nid, scan_start=start + rng.randrange(cycle),
                boot_ms=start - rng.randrange(60_000, 600_000), next_status=start)
        for nid in contract.NODE_IDS
    ]
    sent = Counter()
    next_report = start + 10_000

    while not duration_s or now_ms() - start < duration_s * 1000:
        now = now_ms()
        for n in nodes:
            end = n.scan_start + scan_ms
            if now < end:
                continue
            msgs = simulate_window(n.node_id, n.scan_start, end, devices, sweeps, rng)
            if now >= n.next_status:
                msgs.append(("status", {
                    "ts": now, "node": n.node_id, "uptime_s": (now - n.boot_ms) // 1000,
                    "wifi_rssi": max(-127, min(0, round(-55 + rng.gauss(0, 2)))), "fw": FAKE_FW,
                }))
                n.next_status += status_every_s * 1000
            for kind, payload in msgs:
                send(kind, payload)
                sent[kind] += 1
            n.scan_start += cycle
            if n.scan_start + scan_ms < now:
                n.scan_start = now  # fell behind (laptop was asleep), skip ahead

        if now >= next_report:
            log.info("sent %s in the last 10 s", ", ".join(f"{sent[k]} {k}" for k in contract.KINDS))
            sent.clear()
            next_report += 10_000

        next_due = min(n.scan_start + scan_ms for n in nodes)
        time.sleep(max(0.0, (next_due - now_ms()) / 1000))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Publish fake node readings that follow the MQTT contract.")
    parser.add_argument("--config", type=Path, help="config file (default: server/config.toml if present)")
    parser.add_argument("--host", help="broker host (overrides config)")
    parser.add_argument("--port", type=int, help="broker port (overrides config)")
    parser.add_argument("--duration", type=float, default=0, help="seconds to run (default: until Ctrl+C)")
    parser.add_argument("--seed", type=int, help="random seed, for repeatable runs")
    parser.add_argument("--scan-ms", type=int, default=800, help="scan window length (default: 800)")
    parser.add_argument("--send-ms", type=int, default=200, help="send window length (default: 200)")
    parser.add_argument("--sweeps", type=int, default=20,
                        help="channel sweeps per spectrum message (default: 20, a guess of about "
                             "40 ms per 126-channel sweep in an 800 ms window; measure on a real node)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = load_config(args.config)
    host = args.host or cfg.host
    port = args.port or cfg.port
    salt = cfg.hash_salt
    if not salt:
        salt = secrets.token_hex(16)
        log.info("no hash_salt in server/config.toml, using a random salt for this run")

    rng = random.Random(args.seed)
    devices = default_devices(salt, rng)

    connack = {}
    got_connack = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        connack["rc"] = reason_code
        got_connack.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"invigil-fake-{os.getpid()}")
    if cfg.username:
        client.username_pw_set(cfg.username, cfg.password)
    client.on_connect = on_connect
    try:
        client.connect(host, port, keepalive=30)
    except OSError as e:
        sys.exit(f"cannot reach the MQTT broker at {host}:{port} ({e}). Is Mosquitto running?")
    client.loop_start()
    if not got_connack.wait(5) or connack["rc"].is_failure:
        client.loop_stop()
        sys.exit(f"broker refused the connection: {connack.get('rc', 'no reply')} (check server/config.toml)")

    def send(kind: str, payload: dict) -> None:
        contract.validate(kind, payload, payload["node"])  # never publish anything off-contract
        client.publish(contract.topic(payload["node"], kind), json.dumps(payload, separators=(",", ":")))

    log.info("fake nodes %s publishing to %s:%d (scan %d ms, send %d ms, %d sweeps)",
             ", ".join(contract.NODE_IDS), host, port, args.scan_ms, args.send_ms, args.sweeps)
    log.info("ground truth for this run:")
    for d in devices:
        note = "" if d.adv_interval_ms else "  (not advertising, spectrum only)"
        log.info("  %s  %-10s  %s%s", d.addr, d.kind, d.label, note)

    try:
        run(send, devices, args.scan_ms, args.send_ms, args.sweeps, args.duration, rng)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.loop_stop()
        log.info("stopped")


if __name__ == "__main__":
    main()
