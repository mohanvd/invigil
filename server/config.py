"""Load server settings from server/config.toml.

config.toml holds secrets and is gitignored. Create it from the template:
    copy server\\config.toml.example server\\config.toml      (Windows)
    cp server/config.toml.example server/config.toml          (macOS/Linux)
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("config.toml")
HASH_RE = re.compile(r"[0-9a-f]{12}")
# The detector ignores devices whose median RSSI over a window is below this.
# The empty-room baseline on 2026-11-22 had no device stronger than -86 dBm
# (median), so -85 keeps neighbouring rooms out. Check it with a baseline run
# in the real hall (design requirement 5).
DEFAULT_MIN_RSSI = -85


@dataclass
class Config:
    host: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    hash_salt: str = ""
    # Hashed addresses of devices permitted in the hall, such as the invigilator's phone.
    allowed: tuple[str, ...] = ()
    min_rssi: int = DEFAULT_MIN_RSSI
    loaded_from: Path | None = None


def load_config(path: Path | None = None) -> Config:
    """Read the config file. With no path, a missing default file means defaults."""
    if path is None:
        if not DEFAULT_PATH.exists():
            return Config()
        path = DEFAULT_PATH
    with open(path, "rb") as f:
        data = tomllib.load(f)
    mqtt = data.get("mqtt", {})
    privacy = data.get("privacy", {})
    whitelist = data.get("whitelist", {})
    allowed = tuple(whitelist.get("allowed", []))
    bad = [a for a in allowed if not isinstance(a, str) or not HASH_RE.fullmatch(a)]
    if bad:
        raise ValueError(f"{path}: whitelist.allowed must hold 12-char lowercase hex hashes, not raw addresses")
    return Config(
        host=mqtt.get("host", Config.host),
        port=int(mqtt.get("port", Config.port)),
        username=mqtt.get("username", ""),
        password=mqtt.get("password", ""),
        hash_salt=privacy.get("hash_salt", ""),
        allowed=allowed,
        min_rssi=int(data.get("detector", {}).get("min_rssi", DEFAULT_MIN_RSSI)),
        loaded_from=Path(path),
    )
