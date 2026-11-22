"""Detector: run the saved models on live readings and publish detections.

Run from the repo root (invigil start runs it for you):
    python -m server.detector

Each time a batch of BLE readings arrives (about once a second), and at
least once a second, it looks at the last 5 s of BLE and spectrum readings from each
unit, the same windows the models were trained on (ml/features.py), and
publishes one message per device on invigil/node/{node}/detection
(docs/contract.md, Detections):

- device type: phone, earpiece or smartwatch, or allowed for a hash on the
  whitelist in server/config.toml;
- near (under 1 m from the unit) or not_near.

A device is only reported when it sent at least MIN_ADVS advertisements in
the window and its median RSSI is at least min_rssi (server/config.toml), so
devices in neighbouring rooms stay out.

The models come from python -m ml.train, which writes ml/models/type.joblib
and ml/models/band.joblib.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from collections import deque
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import paho.mqtt.client as mqtt

from ml.features import CHANNEL_COLS, MIN_ADVS, WINDOW_S, ble_features, spectrum_features
from server import contract
from server.config import Config, load_config

log = logging.getLogger("invigil.detector")

MODELS_DIR = Path("ml/models")
STEP_S = 1.0  # at least one decision a second, over the last WINDOW_S seconds
# The unit sends a scan window's readings in one or more ble messages right
# after the window ends. The detector decides as soon as they arrive, after
# waiting this long for the rest of the batch, so an alert does not sit
# waiting for the next tick (design requirement 4, alert latency).
BATCH_WAIT_S = 0.05
MIN_GAP_S = 0.5  # never decide twice for the same batch


class MissingModels(RuntimeError):
    pass


def load_models(models_dir: Path = MODELS_DIR) -> dict:
    """{"type": {...}, "band": {...}} as saved by ml.train."""
    models = {}
    for target in ("type", "band"):
        path = Path(models_dir) / f"{target}.joblib"
        if not path.exists():
            raise MissingModels(f"{path} is missing. Train the models first: python -m ml.train")
        models[target] = joblib.load(path)
    return models


def models_present(models_dir: Path = MODELS_DIR) -> bool:
    return all((Path(models_dir) / f"{t}.joblib").exists() for t in ("type", "band"))


def _predict(saved: dict, feats: dict) -> tuple[str, float]:
    """The most likely class and its probability."""
    X = np.array([[feats[c] for c in saved["features"]]], dtype=float)
    proba = saved["model"].predict_proba(X)[0]
    best = int(np.argmax(proba))
    return str(saved["model"].classes_[best]), float(proba[best])


class Detector:
    """Keeps the last window of readings and turns it into detections."""

    def __init__(self, models: dict, allowed: tuple[str, ...] = (), min_rssi: float = -85,
                 window_ms: int = int(WINDOW_S * 1000)):
        self.models = models
        self.allowed = set(allowed)
        self.min_rssi = min_rssi
        self.window_ms = window_ms
        self._ble: deque[tuple[str, int, str, int, str]] = deque()  # node, ts, addr, rssi, mfr
        self._spectrum: deque[tuple[str, int, int, list[int]]] = deque()  # node, ts, sweeps, hits
        self._lock = threading.Lock()

    def add(self, kind: str, payload: dict) -> None:
        """A validated ble or spectrum message from a unit."""
        with self._lock:
            if kind == "ble":
                for r in payload["readings"]:
                    self._ble.append((payload["node"], r["ts"], r["addr"], r["rssi"], r["mfr"] or ""))
            elif kind == "spectrum":
                self._spectrum.append((payload["node"], payload["ts"], payload["sweeps"], payload["hits"]))

    def _prune(self, cutoff: int) -> None:
        # Readings arrive in batches, roughly in time order, so trimming from the
        # left keeps the buffer small; the window filter below does the exact cut.
        while self._ble and self._ble[0][1] < cutoff - self.window_ms:
            self._ble.popleft()
        while self._spectrum and self._spectrum[0][1] < cutoff - self.window_ms:
            self._spectrum.popleft()

    def decide(self, now_ms: int) -> list[dict]:
        """Detections for readings with ts in [now_ms - window, now_ms)."""
        t0 = now_ms - self.window_ms
        with self._lock:
            self._prune(t0)
            ble = [r for r in self._ble if t0 <= r[1] < now_ms]
            spec = [s for s in self._spectrum if t0 <= s[1] < now_ms]

        out = []
        by_device: dict[tuple[str, str], list[tuple[int, int, str]]] = {}
        for node, ts, addr, rssi, mfr in ble:
            by_device.setdefault((node, addr), []).append((ts, rssi, mfr))
        for (node, addr), rows in sorted(by_device.items()):
            if len(rows) < MIN_ADVS:
                continue
            rows.sort()
            ts = np.array([r[0] for r in rows], dtype=np.int64)
            rssi = np.array([r[1] for r in rows], dtype=float)
            if np.median(rssi) < self.min_rssi:
                continue
            mfr = pd.Series([r[2] for r in rows]).mode().iat[0]
            feats = ble_features(ts, rssi, mfr)
            feats.update(spectrum_features(_spectrum_frame([s for s in spec if s[0] == node])))

            if addr in self.allowed:
                dtype, type_conf = "allowed", 1.0
            else:
                dtype, type_conf = _predict(self.models["type"], feats)
            band, band_conf = _predict(self.models["band"], feats)
            out.append({
                "ts": int(ts[-1]),  # the last reading used, on the unit's clock
                "node": node,
                "addr": addr,
                "type": dtype,
                "type_conf": round(type_conf, 3),
                "band": band,
                "band_conf": round(band_conf, 3),
                "rssi": int(round(float(np.median(rssi)))),
            })
        return out


def _spectrum_frame(rows: list[tuple[str, int, int, list[int]]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["sweeps", *CHANNEL_COLS])
    data = [[sweeps, *hits] for _, _, sweeps, hits in rows]
    return pd.DataFrame(data, columns=["sweeps", *CHANNEL_COLS])


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def run(cfg: Config, detector: Detector, host: str, port: int) -> None:
    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("broker refused the connection: %s (check server/config.toml)", reason_code)
            return
        for kind in ("ble", "spectrum"):
            client.subscribe(f"{contract.TOPIC_ROOT}/+/{kind}")
        log.info("connected to %s:%d", host, port)

    fresh = threading.Event()

    def on_message(client, userdata, msg):
        try:
            node, kind = contract.parse_topic(msg.topic)
            payload = contract.validate(kind, json.loads(msg.payload), node)
        except ValueError:
            return  # the logger counts and reports bad messages
        detector.add(kind, payload)
        if kind == "ble":
            fresh.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"invigil-detector-{os.getpid()}")
    if cfg.username:
        client.username_pw_set(cfg.username, cfg.password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect_async(host, port, keepalive=30)
    client.loop_start()

    sent = 0
    last_report = last_decision = time.monotonic()
    try:
        while True:
            # Decide when a ble batch arrives, or after STEP_S without one.
            if fresh.wait(timeout=STEP_S):
                time.sleep(BATCH_WAIT_S)
            fresh.clear()
            if time.monotonic() - last_decision < MIN_GAP_S:
                continue
            last_decision = time.monotonic()
            for d in detector.decide(now_ms()):
                payload = contract.validate("detection", d, d["node"])
                client.publish(contract.topic(d["node"], "detection"), contract.encode(payload))
                sent += 1
            if time.monotonic() - last_report >= 10:
                log.info("published %d detections in the last 10 s", sent)
                sent, last_report = 0, time.monotonic()
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.loop_stop()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Publish Invigil detections from live readings.")
    parser.add_argument("--config", type=Path, help="config file (default: server/config.toml if present)")
    parser.add_argument("--models", type=Path, default=MODELS_DIR, help="folder with type.joblib and band.joblib")
    parser.add_argument("--host", help="broker host (overrides config)")
    parser.add_argument("--port", type=int, help="broker port (overrides config)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = load_config(args.config)
    try:
        models = load_models(args.models)
    except MissingModels as e:
        raise SystemExit(str(e)) from None
    detector = Detector(models, cfg.allowed, cfg.min_rssi)
    log.info("whitelist: %d device(s), min RSSI %d dBm", len(cfg.allowed), cfg.min_rssi)
    run(cfg, detector, args.host or cfg.host, args.port or cfg.port)


if __name__ == "__main__":
    main()
