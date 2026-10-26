"""Start background processes and stop exactly those, by PID.

Every process the launcher starts is written to .invigil/run.json with its PID
and its start time. stop() only acts on a PID whose start time still matches,
so a PID that Windows has since given to another program is never touched.
Nothing is ever stopped by name.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import zlib
from pathlib import Path

from invigil import ROOT, STATE_DIR

RUN_FILE = STATE_DIR / "run.json"
LOG_DIR = STATE_DIR / "logs"


# --- process identity -------------------------------------------------------


def start_time(pid: int) -> int | None:
    """When the process started, as an opaque number. None if it is not running."""
    if sys.platform == "win32":
        return _start_time_windows(pid)
    return _start_time_posix(pid)


def _start_time_windows(pid: int) -> int | None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    process_query_limited_information = 0x1000
    still_active = 259
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != still_active:
            return None
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)
        ):
            return None
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        kernel32.CloseHandle(handle)


def _start_time_posix(pid: int) -> int | None:
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            text = stat.read_text()
        except OSError:
            return None
        # Field 22 is the start time. The command name (field 2) may hold spaces,
        # so count from the closing parenthesis.
        fields = text[text.rindex(")") + 2 :].split()
        if fields[0] == "Z":  # zombie: exited, not reaped yet
            return None
        return int(fields[19])
    out = subprocess.run(["ps", "-o", "lstart=,stat=", "-p", str(pid)], capture_output=True, text=True)
    line = out.stdout.strip()
    if out.returncode != 0 or not line or line.split()[-1].startswith("Z"):
        return None
    return zlib.crc32(line.rsplit(None, 1)[0].encode())


def is_running(record: dict) -> bool:
    """True only if the PID is alive and is still the process the launcher started."""
    return record.get("started") is not None and start_time(record["pid"]) == record["started"]


# --- run.json ---------------------------------------------------------------


def load_run(path: Path = RUN_FILE) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return data.get("processes", []) if isinstance(data, dict) else []


def save_run(records: list[dict], path: Path = RUN_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if records:
        path.write_text(json.dumps({"processes": records}, indent=2) + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


# --- start and stop ---------------------------------------------------------


def spawn(name: str, cmd: list[str], log_dir: Path = LOG_DIR, env: dict | None = None, **info) -> dict:
    """Start cmd in the background with its output going to a log file.

    The process does not belong to the terminal that started it, so closing
    that window does not stop it. Returns the record to keep in run.json.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env, **kwargs
        )
    started = None
    for _ in range(50):
        started = start_time(proc.pid)
        if started is not None or proc.poll() is not None:
            break
        time.sleep(0.02)
    return {"name": name, "pid": proc.pid, "started": started, "cmd": cmd, "log": str(log_path), **info}


def stop(record: dict, timeout: float = 5.0) -> str:
    """Stop one recorded process and its children. Returns what happened."""
    if not is_running(record):
        return "not running"
    pid = record["pid"]
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(pid, signal.SIGTERM)  # spawn() made it a session leader, so pgid == pid
        except ProcessLookupError:
            return "not running"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_running(record):
            return "stopped"
        time.sleep(0.1)
    return "still running"


def tail(path: str | Path, lines: int = 15) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-lines:])
