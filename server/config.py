"""Load server settings from server/config.toml.

config.toml holds secrets and is gitignored. Create it from the template:
    copy server\\config.toml.example server\\config.toml      (Windows)
    cp server/config.toml.example server/config.toml          (macOS/Linux)
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("config.toml")


@dataclass
class Config:
    host: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    hash_salt: str = ""
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
    return Config(
        host=mqtt.get("host", Config.host),
        port=int(mqtt.get("port", Config.port)),
        username=mqtt.get("username", ""),
        password=mqtt.get("password", ""),
        hash_salt=privacy.get("hash_salt", ""),
        loaded_from=Path(path),
    )
