"""MQTT logger: record every valid node reading to CSV.

Run from the repo root:
    python -m server.logger --session calib-n1

Writes data/raw/<date>-<session>/ble.csv, spectrum.csv and status.csv.
Each row starts with rx_ts, the laptop time (ms since epoch) when the message
arrived, so rx_ts - ts is the node-to-laptop latency.

Messages that break the MQTT contract are counted and reported on the console
but never written to disk, so a firmware bug cannot leak raw data into a file.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import statistics
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

from server import contract
from server.config import load_config

log = logging.getLogger("invigil.logger")

COLUMNS = {
    "ble": ["rx_ts", *contract.FIELDS["ble"]],
    "spectrum": ["rx_ts", "ts", "node", "sweeps"]
    + [f"ch{c:03d}" for c in range(contract.NUM_CHANNELS)],
    "status": ["rx_ts", *contract.FIELDS["status"]],
}


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def to_row(kind: str, payload: dict, rx_ts: int) -> list:
    if kind == "spectrum":
        return [rx_ts, payload["ts"], payload["node"], payload["sweeps"], *payload["hits"]]
    # A null mfr is written as an empty cell.
    return [rx_ts, *(payload[k] for k in contract.FIELDS[kind])]


class CsvSink:
    """One CSV file per message kind. Appends, and flushes after every row."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self._files = {}
        self._writers = {}

    def write(self, kind: str, row: list) -> None:
        if kind not in self._writers:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            path = self.out_dir / f"{kind}.csv"
            is_new = not path.exists() or path.stat().st_size == 0
            f = open(path, "a", newline="", encoding="utf-8")
            writer = csv.writer(f)
            if is_new:
                writer.writerow(COLUMNS[kind])
            self._files[kind] = f
            self._writers[kind] = writer
        self._writers[kind].writerow(row)
        self._files[kind].flush()

    def close(self) -> None:
        for f in self._files.values():
            f.close()
        self._files.clear()
        self._writers.clear()


class Recorder:
    """Checks each message against the contract, writes the good ones, counts the rest."""

    def __init__(self, sink: CsvSink):
        self.sink = sink
        self.total = 0
        self._lock = threading.Lock()
        self._accepted = Counter()  # (node, kind) -> count since last report
        self._rejected = Counter()  # reason -> count since last report
        self._latencies = []  # rx_ts - ts, ms, since last report
        self._warned = set()

    def handle(self, topic: str, raw: bytes, rx_ts: int) -> bool:
        try:
            node, kind = contract.parse_topic(topic)
            payload = contract.validate(kind, json.loads(raw), node)
        except ValueError as e:  # ContractError, bad JSON, bad UTF-8
            reason = str(e) if isinstance(e, contract.ContractError) else "not valid JSON"
            with self._lock:
                self._rejected[reason] += 1
                first_time = (topic, reason) not in self._warned
                self._warned.add((topic, reason))
            if first_time:
                log.warning("rejected %s: %s (repeats are only counted)", topic, reason)
            return False

        with self._lock:
            self.sink.write(kind, to_row(kind, payload, rx_ts))
            self.total += 1
            self._accepted[(node, kind)] += 1
            self._latencies.append(rx_ts - payload["ts"])
        return True

    def report(self) -> str:
        """One summary line for everything since the last call."""
        with self._lock:
            accepted, self._accepted = self._accepted, Counter()
            rejected, self._rejected = self._rejected, Counter()
            latencies, self._latencies = self._latencies, []

        parts = []
        for node in contract.NODE_IDS:
            counts = [f"{accepted[(node, k)]} {k}" for k in contract.KINDS if accepted[(node, k)]]
            parts.append(f"{node}: {', '.join(counts) if counts else 'silent'}")
        if latencies:
            parts.append(
                f"latency p50 {statistics.median(latencies):.0f} ms, max {max(latencies)} ms"
            )
        parts.append(f"rejected {sum(rejected.values())}")
        return " | ".join(parts)

    def close(self) -> None:
        with self._lock:
            self.sink.close()


def session_dir(base: Path, session: str | None) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    name = session or datetime.now().strftime("%H%M%S")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise SystemExit("--session may only use letters, digits, '.', '_' and '-'")
    return base / f"{today}-{name}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Record Invigil node readings to CSV.")
    parser.add_argument("--session", help="name for this recording, e.g. calib-n1 (default: time now)")
    parser.add_argument("--out", type=Path, default=Path("data/raw"), help="base folder (default: data/raw)")
    parser.add_argument("--config", type=Path, help="config file (default: server/config.toml if present)")
    parser.add_argument("--host", help="broker host (overrides config)")
    parser.add_argument("--port", type=int, help="broker port (overrides config)")
    parser.add_argument("--report-every", type=float, default=10.0, help="seconds between summary lines")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = load_config(args.config)
    host = args.host or cfg.host
    port = args.port or cfg.port
    out_dir = session_dir(args.out, args.session)
    recorder = Recorder(CsvSink(out_dir))

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("broker refused the connection: %s (check server/config.toml)", reason_code)
            return
        client.subscribe(contract.SUBSCRIPTION)
        log.info("connected to %s:%d, subscribed to %s", host, port, contract.SUBSCRIPTION)

    def on_connect_fail(client, userdata):
        log.error("cannot reach the broker at %s:%d, retrying. Is Mosquitto running?", host, port)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.warning("disconnected from broker (%s), reconnecting", reason_code)

    def on_message(client, userdata, msg):
        recorder.handle(msg.topic, msg.payload, now_ms())

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"invigil-logger-{os.getpid()}")
    if cfg.username:
        client.username_pw_set(cfg.username, cfg.password)
    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect_async(host, port, keepalive=30)
    client.loop_start()

    log.info("writing to %s (Ctrl+C to stop)", out_dir)
    try:
        while True:
            time.sleep(args.report_every)
            log.info(recorder.report())
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.loop_stop()
        recorder.close()
        log.info("stopped. %d rows written to %s", recorder.total, out_dir)


if __name__ == "__main__":
    main()
