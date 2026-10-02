"""The Invigil MQTT contract: topics, payload checks, and address hashing.

This module is the contract between the node firmware and the laptop. The
logger rejects anything that does not pass validate(), and the fake publisher
runs every message through it before sending, so the two can never drift apart.
"""

from __future__ import annotations

import hashlib
import re

TOPIC_ROOT = "invigil/node"
SUBSCRIPTION = f"{TOPIC_ROOT}/+/+"
# One sensor unit for now. Phase 2 adds units here; the topic format stays the same.
NODE_IDS = ("N1",)
NUM_CHANNELS = 126  # nRF24L01 channels 0..125, channel c is 2400 + c MHz

FIELDS = {
    "ble": ("ts", "node", "addr", "rssi", "mfr"),
    "spectrum": ("ts", "node", "sweeps", "hits"),
    "status": ("ts", "node", "uptime_s", "wifi_rssi", "fw"),
}
KINDS = tuple(FIELDS)

# Timestamps are milliseconds since epoch. A value below MIN_TS_MS means the
# node has not synced NTP yet, or it sent seconds instead of milliseconds.
# A value above MAX_TS_MS usually means microseconds.
MIN_TS_MS = 1_600_000_000_000  # 2020-09-13
MAX_TS_MS = 9_999_999_999_999  # 2286-11-20

_ADDR_RE = re.compile(r"[0-9a-f]{12}")
_MFR_RE = re.compile(r"0x[0-9A-F]{4}")


class ContractError(ValueError):
    """A topic or payload does not follow the MQTT contract."""


def topic(node: str, kind: str) -> str:
    if node not in NODE_IDS:
        raise ContractError(f"unknown node {node!r}")
    if kind not in FIELDS:
        raise ContractError(f"unknown kind {kind!r}")
    return f"{TOPIC_ROOT}/{node}/{kind}"


def parse_topic(name: str) -> tuple[str, str]:
    """Split 'invigil/node/N1/ble' into ('N1', 'ble')."""
    parts = name.split("/")
    if len(parts) != 4 or "/".join(parts[:2]) != TOPIC_ROOT:
        raise ContractError(f"topic is not {TOPIC_ROOT}/<node>/<kind>")
    node, kind = parts[2], parts[3]
    topic(node, kind)  # raises if either part is unknown
    return node, kind


def validate(kind: str, payload: object, node: str | None = None) -> dict:
    """Check a decoded JSON payload against the contract.

    Returns the payload unchanged if it is valid. Raises ContractError with a
    short reason otherwise. Error messages name fields but never echo values,
    so a bad message cannot leak a raw address into the console log.
    """
    if kind not in FIELDS:
        raise ContractError(f"unknown kind {kind!r}")
    if not isinstance(payload, dict):
        raise ContractError("payload must be a JSON object")

    expected = FIELDS[kind]
    missing = [k for k in expected if k not in payload]
    if missing:
        raise ContractError(f"missing field(s): {', '.join(missing)}")
    extra = sorted(k for k in payload if k not in expected)
    if extra:
        raise ContractError(f"unexpected field(s): {', '.join(extra)}")

    ts = _int(payload, "ts", 0, MAX_TS_MS)
    if ts < MIN_TS_MS:
        raise ContractError("ts is too small: node clock not synced with NTP, or seconds sent instead of ms")
    if payload["node"] not in NODE_IDS:
        raise ContractError("node must be one of " + ", ".join(NODE_IDS))
    if node is not None and payload["node"] != node:
        raise ContractError("node in payload does not match node in topic")

    if kind == "ble":
        addr = payload["addr"]
        if not isinstance(addr, str) or not _ADDR_RE.fullmatch(addr):
            raise ContractError("addr must be a hashed address: 12 lowercase hex chars")
        _int(payload, "rssi", -127, 0)
        mfr = payload["mfr"]
        # null is allowed: many advertisements carry no manufacturer data.
        if mfr is not None and (not isinstance(mfr, str) or not _MFR_RE.fullmatch(mfr)):
            raise ContractError('mfr must be null or a company ID like "0x004C"')

    elif kind == "spectrum":
        sweeps = _int(payload, "sweeps", 1, 65_535)
        hits = payload["hits"]
        if not isinstance(hits, list) or len(hits) != NUM_CHANNELS:
            raise ContractError(f"hits must be a list of {NUM_CHANNELS} integers")
        for h in hits:
            if isinstance(h, bool) or not isinstance(h, int) or not 0 <= h <= sweeps:
                raise ContractError("each hit count must be an integer from 0 to sweeps")

    elif kind == "status":
        _int(payload, "uptime_s", 0, 2**31 - 1)
        _int(payload, "wifi_rssi", -127, 0)
        fw = payload["fw"]
        if not isinstance(fw, str) or not 1 <= len(fw) <= 32:
            raise ContractError("fw must be a version string of 1 to 32 chars")

    return payload


def _int(payload: dict, key: str, lo: int, hi: int) -> int:
    value = payload[key]
    # bool is a subclass of int in Python, but true/false is never a valid reading.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{key} must be an integer")
    if not lo <= value <= hi:
        raise ContractError(f"{key} is out of range {lo}..{hi}")
    return value


def hash_addr(mac: str | bytes, salt: str) -> str:
    """Anonymize a BLE address: salted SHA-256, first 12 hex chars.

    digest = sha256(salt as UTF-8 bytes + the 6 address bytes)

    The address bytes go most significant first, in the order the address is
    normally printed (AA:BB:CC:DD:EE:FF). Firmware must hash exactly the same
    way so hashes from nodes, the whitelist, and fake data all agree.

    The firmware gets addresses from BTstack. The order BTstack hands over
    the 6 bytes is not assumed here: the firmware must reproduce the test
    vector in the README, and that is checked on real hardware at boot. If
    the unit prints the "wrong byte order" hash from the README instead, it
    must reverse the bytes before hashing.
    """
    if isinstance(mac, str):
        mac = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    if len(mac) != 6:
        raise ValueError("a BLE address is 6 bytes")
    return hashlib.sha256(salt.encode("utf-8") + mac).hexdigest()[:12]
