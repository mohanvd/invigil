"""Find Mosquitto, and check the ports and the Windows Mosquitto service."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from invigil import ROOT

CONF = ROOT / "server" / "mosquitto.conf"
PASSWD = ROOT / "server" / "mosquitto.passwd"
MQTT_PORT = 1883
# The WebSockets listener in server/mosquitto.conf, for the dashboard.
WS_PORT = 9001
SERVICE = "mosquitto"

STOP_SERVICE_HELP = (
    "The Windows Mosquitto service is holding {port}. It only listens on localhost\n"
    "and has no WebSockets listener, so the unit and the dashboard cannot use it.\n"
    "Stop it from a terminal run as administrator:\n"
    "    net stop mosquitto\n"
    "To keep it from starting again at boot:\n"
    "    sc config mosquitto start= demand"
)
PORT_BUSY_HELP = (
    "Something else is already listening on {port}. If it is a Mosquitto you\n"
    "started by hand, stop it (Ctrl+C in its window), then run start again."
)


def find_mosquitto() -> Path | None:
    found = shutil.which("mosquitto")
    if found:
        return Path(found)
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if base and (Path(base) / "mosquitto" / "mosquitto.exe").exists():
            return Path(base) / "mosquitto" / "mosquitto.exe"
    return None


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """True if something accepts connections on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def parse_sc_query(output: str) -> str | None:
    """The STATE from `sc query` output, for example "RUNNING". None if absent."""
    for line in output.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "STATE":
            parts = value.split()
            return parts[1] if len(parts) > 1 else None
    return None


def service_state(name: str = SERVICE) -> str | None:
    """State of a Windows service, or None if there is no such service (or not Windows)."""
    if sys.platform != "win32":
        return None
    out = subprocess.run(["sc", "query", name], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return parse_sc_query(out.stdout)


def busy_port_help(ports: list[int], state: str | None) -> str:
    """What to tell the user when the broker's ports are already taken."""
    port = ("port " if len(ports) == 1 else "ports ") + " and ".join(str(p) for p in ports)
    if state == "RUNNING":
        return STOP_SERVICE_HELP.format(port=port)
    return PORT_BUSY_HELP.format(port=port)


def mosquitto_cmd(exe: Path) -> list[str]:
    # No -v: verbose mode logs every publish and the log file would grow fast.
    return [str(exe), "-c", str(CONF.relative_to(ROOT))]
