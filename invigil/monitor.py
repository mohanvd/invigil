"""Watch the unit's MQTT traffic: online or not, last status, message rates.

Every message goes through server/contract.py, the same check the logger
uses, so a message the logger would reject is counted as rejected here too.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import paho.mqtt.client as mqtt

from server import contract
from server.config import Config

# The unit sends a status message every 10 s. Three missed ones mean offline.
ONLINE_S = 30.0
RATE_WINDOW_S = 10.0


@dataclass
class NodeView:
    node: str
    online: bool
    last_status: dict | None
    status_age_s: float | None
    rates: dict[str, float] = field(default_factory=dict)


class UnitMonitor:
    def __init__(self, window_s: float = RATE_WINDOW_S):
        self.window_s = window_s
        self.rejected = 0
        self.connected = False
        self.connect_error = ""
        self._lock = threading.Lock()
        self._times = {(n, k): deque() for n in contract.NODE_IDS for k in contract.KINDS}
        self._status: dict[str, tuple[dict, float]] = {}
        self.status_seen = threading.Event()

    def handle(self, topic: str, raw: bytes, now: float) -> bool:
        try:
            node, kind = contract.parse_topic(topic)
            payload = contract.validate(kind, json.loads(raw), node)
        except ValueError:
            with self._lock:
                self.rejected += 1
            return False
        with self._lock:
            self._times[(node, kind)].append(now)
            if kind == "status":
                self._status[node] = (payload, now)
        if kind == "status":
            self.status_seen.set()
        return True

    def view(self, node: str, now: float, listened_s: float | None = None) -> NodeView:
        """What is known about one unit. listened_s shortens the rate window
        when the monitor has been running for less than a full window."""
        window = min(self.window_s, listened_s) if listened_s else self.window_s
        with self._lock:
            rates = {}
            for kind in contract.KINDS:
                times = self._times[(node, kind)]
                while times and times[0] < now - self.window_s:
                    times.popleft()
                rates[kind] = sum(1 for t in times if t >= now - window) / window if window > 0 else 0.0
            status, at = self._status.get(node, (None, None))
        age = None if at is None else now - at
        return NodeView(node, age is not None and age <= ONLINE_S, status, age, rates)


def connect(cfg: Config, on_message, name: str) -> tuple[mqtt.Client, threading.Event, list[str]]:
    """Connect to the broker in the background and subscribe to every unit topic.

    Returns the client, an event set once subscribed, and a list that gets the
    reason if the broker refuses the login.
    """
    ready = threading.Event()
    errors: list[str] = []

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            errors.append(str(reason_code))
            return
        client.subscribe(contract.SUBSCRIPTION)
        ready.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"invigil-{name}-{os.getpid()}")
    if cfg.username:
        client.username_pw_set(cfg.username, cfg.password)
    client.on_connect = on_connect
    client.on_message = lambda c, u, msg: on_message(msg.topic, msg.payload)
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    client.connect_async(cfg.host, cfg.port, keepalive=30)
    client.loop_start()
    return client, ready, errors


def watch(cfg: Config, monitor: UnitMonitor) -> mqtt.Client:
    client, ready, errors = connect(cfg, lambda t, p: monitor.handle(t, p, time.monotonic()), "status")
    if ready.wait(5):
        monitor.connected = True
    else:
        monitor.connect_error = errors[0] if errors else f"no answer from {cfg.host}:{cfg.port}"
    return client


def close(client: mqtt.Client) -> None:
    client.disconnect()
    client.loop_stop()
