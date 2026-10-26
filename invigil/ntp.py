"""Measure the laptop clock against an NTP server (SNTP, RFC 4330).

Latency is rx_ts (laptop clock) minus ts (unit clock, set by SNTP), so the
laptop clock has to be right too before any latency number means anything.
"""

from __future__ import annotations

import json
import socket
import struct
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SERVER = "pool.ntp.org"
WARN_MS = 100
NTP_EPOCH_OFFSET = 2_208_988_800  # seconds from 1900-01-01 to 1970-01-01
SYNC_HELP = "Sync it: Settings > Time & language > Date & time > Sync now."


def to_ntp(t: float) -> bytes:
    secs = int(t) + NTP_EPOCH_OFFSET
    frac = int((t % 1) * 2**32)
    return struct.pack("!II", secs, frac)


def from_ntp(b: bytes) -> float:
    secs, frac = struct.unpack("!II", b)
    return secs - NTP_EPOCH_OFFSET + frac / 2**32


def offset_and_delay(t1: float, t2: float, t3: float, t4: float) -> tuple[float, float]:
    """t1 sent, t2 server received, t3 server sent, t4 received. Seconds.

    A positive offset means the laptop clock is behind the server.
    """
    return ((t2 - t1) + (t3 - t4)) / 2, (t4 - t1) - (t3 - t2)


def query(server: str = DEFAULT_SERVER, port: int = 123, timeout: float = 2.0) -> tuple[float, float]:
    """One SNTP request. Returns (offset, round trip delay) in seconds."""
    request = bytearray(48)
    request[0] = 0x23  # LI 0, version 4, mode 3 (client)
    t1 = time.time()
    request[40:48] = to_ntp(t1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(bytes(request), (server, port))
        while True:
            data, _ = sock.recvfrom(512)
            t4 = time.time()
            # Ignore anything that is not the answer to this request.
            if len(data) >= 48 and data[24:32] == bytes(request[40:48]):
                break
    if data[0] & 0x07 != 4 or data[1] == 0:
        raise OSError("not a valid server reply")
    return offset_and_delay(t1, from_ntp(data[32:40]), from_ntp(data[40:48]), t4)


@dataclass
class ClockCheck:
    server: str
    offset_ms: float | None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.offset_ms is not None and abs(self.offset_ms) <= WARN_MS

    def describe(self) -> str:
        if self.offset_ms is None:
            return f"could not reach {self.server} ({self.error}), offset unknown"
        # The offset is server minus laptop. Describe it from the laptop's side.
        side = "behind" if self.offset_ms > 0 else "ahead of"
        text = f"{abs(self.offset_ms):.0f} ms {side} {self.server}"
        if not self.ok:
            text += f". WARNING: more than {WARN_MS} ms off, latency results are not valid. {SYNC_HELP}"
        return text


def record(folder: Path, when: str, check: ClockCheck, now: float | None = None) -> Path:
    """Add one clock measurement to <session folder>/clock.json under "start" or "stop".

    laptop_minus_ntp_ms is how far the laptop clock (rx_ts) was ahead of NTP.
    Subtract it from rx_ts - ts to correct a latency figure.
    """
    path = Path(folder) / "clock.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[when] = {
        "measured_at_ms": int((time.time() if now is None else now) * 1000),
        "server": check.server,
        "laptop_minus_ntp_ms": None if check.offset_ms is None else round(-check.offset_ms, 1),
        "error": check.error,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def check_clock(server: str = DEFAULT_SERVER, port: int = 123, timeout: float = 2.0) -> ClockCheck:
    try:
        offset, _ = query(server, port, timeout)
    except (OSError, socket.timeout) as e:
        return ClockCheck(server, None, str(e) or type(e).__name__)
    return ClockCheck(server, offset * 1000)
