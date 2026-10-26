"""python -m invigil start | stop | status | calibrate | shortcut"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from invigil import ROOT, broker, calibrate, dashboard, monitor, ntp, procs
from server import contract
from server.config import load_config
from server.logger import session_dir

STATUS_LISTEN_S = 12  # a little over the unit's 10 s status interval
REFRESH_S = 2


def ask_yes(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    return input(f"{prompt} [y/N]: ").strip().lower() in ("y", "yes")


def fmt_uptime(seconds: int) -> str:
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def fmt_rate(rate: float) -> str:
    return f"{rate:.1f}/s" if rate >= 0.1 or rate == 0 else f"1 per {1 / rate:.0f} s"


def describe_process(records: list[dict], name: str) -> dict | None:
    return next((r for r in records if r["name"] == name and procs.is_running(r)), None)


def render(
    records: list[dict],
    mon: monitor.UnitMonitor,
    client_connected: bool,
    clock: ntp.ClockCheck,
    host: str,
    port: int,
    now: float,
    listened_s: float | None = None,
) -> str:
    """The status screen, as text."""
    lines = [f"Invigil  {datetime.now():%Y-%m-%d %H:%M:%S}", ""]
    mq = describe_process(records, "mosquitto")
    if client_connected:
        who = f"started by the launcher, PID {mq['pid']}" if mq else "not started by the launcher"
        lines.append(f"Broker       running at {host}:{port} ({who})")
    else:
        lines.append(f"Broker       NOT reachable at {host}:{port} {mon.connect_error}".rstrip())
    lg = describe_process(records, "logger")
    lines.append(f"Logger       {lg['out']} (PID {lg['pid']})" if lg else "Logger       not running")
    web = describe_process(records, "dashboard")
    lines.append(f"Dashboard    {web['url']} (PID {web['pid']})" if web else "Dashboard    not running")
    for node in contract.NODE_IDS:
        view = mon.view(node, now, listened_s)
        if view.status_age_s is None:
            state = "no status message yet"
        elif view.online:
            state = "online"
        else:
            state = f"OFFLINE, last status {view.status_age_s:.0f} s ago"
        lines.append(f"Unit {node:<8}{state}")
        if view.last_status:
            s = view.last_status
            lines.append(
                f"Last status  uptime {fmt_uptime(s['uptime_s'])}, Wi-Fi RSSI {s['wifi_rssi']} dBm, "
                f"fw {s['fw']}, {view.status_age_s:.0f} s ago"
            )
        rates = ", ".join(f"{k} {fmt_rate(view.rates[k])}" for k in contract.KINDS)
        lines.append(f"Messages     {rates}, rejected {mon.rejected}")
    lines.append(f"Laptop clock {clock.describe()}")
    return "\n".join(lines)


def preflight(cfg) -> list[str]:
    """Everything that would stop start from working. Empty if all is well."""
    problems = []
    if cfg.loaded_from is None:
        problems.append("server/config.toml is missing. Copy server/config.toml.example and fill it in.")
    elif not cfg.username:
        problems.append("server/config.toml has no MQTT username. The broker requires a login.")
    if not broker.PASSWD.exists():
        problems.append(
            "server/mosquitto.passwd is missing. Create it (it asks for the password):\n"
            "    mosquitto_passwd -c server/mosquitto.passwd invigil"
        )
    if broker.find_mosquitto() is None:
        problems.append("Mosquitto is not installed: https://mosquitto.org/download/")
    return problems


def ensure_dashboard() -> bool:
    if dashboard.needs_install():
        print("The dashboard needs its packages installed first (pnpm install, about 300 MB, needs internet).")
        if not ask_yes("Install them now?"):
            print("Not installed. Run start again when you are ready.")
            return False
        if dashboard.run_pnpm(["install", "--frozen-lockfile"]) != 0:
            return False
    if dashboard.needs_build():
        print("Building the dashboard ...")
        if dashboard.run_pnpm(["build"]) != 0:
            return False
    return True


def cmd_start(args) -> int:
    records = procs.load_run()
    running = [r for r in records if procs.is_running(r)]
    if running:
        print("Already running: " + ", ".join(f"{r['name']} (PID {r['pid']})" for r in running))
        print("Showing the status screen. Stop everything with: invigil stop")
        return show_status(args, records, live=True, wait_for_unit=False)

    cfg = load_config()
    problems = preflight(cfg)
    busy = [p for p in (broker.MQTT_PORT, broker.WS_PORT) if broker.port_open(p)]
    if busy:
        problems.append(broker.busy_port_help(busy, broker.service_state()))
    if broker.port_open(args.port):
        problems.append(f"Port {args.port} is in use. Pick another one with --port.")
    if problems:
        print("Cannot start:\n")
        print("\n\n".join(problems))
        return 1

    clock = ntp.check_clock(args.ntp_server)
    print(f"Laptop clock {clock.describe()}")
    if not ensure_dashboard():
        return 1

    records = []
    try:
        mq = procs.spawn("mosquitto", broker.mosquitto_cmd(broker.find_mosquitto()))
        records.append(mq)
        procs.save_run(records)
        if not wait_for_port(broker.MQTT_PORT, 10):
            print("Mosquitto did not start. Its log:\n" + procs.tail(mq["log"]))
            stop_all(records)
            return 1

        name = args.session or f"live-{datetime.now():%H%M%S}"
        out = session_dir(Path("data/raw"), name)
        lg = procs.spawn("logger", [sys.executable, "-m", "server.logger", "--session", name], out=str(out))
        records.append(lg)
        procs.save_run(records)

        url = dashboard.live_url(args.port, f"ws://localhost:{broker.WS_PORT}", cfg.username)
        web = procs.spawn("dashboard", dashboard.serve_cmd(args.port), url=f"http://127.0.0.1:{args.port}")
        records.append(web)
        procs.save_run(records)
        if not wait_for_port(args.port, 10):
            print("The dashboard server did not start. Its log:\n" + procs.tail(web["log"]))
            stop_all(records)
            return 1
    except KeyboardInterrupt:
        stop_all(records)
        return 1

    print(f"Started. Logs are in {procs.LOG_DIR}. Stop everything with: invigil stop")
    return show_status(args, records, live=True, wait_for_unit=True, clock=clock, open_url=url)


def wait_for_port(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if broker.port_open(port):
            return True
        time.sleep(0.2)
    return False


def show_status(args, records, live: bool, wait_for_unit: bool, clock=None, open_url: str | None = None) -> int:
    cfg = load_config()
    clock = clock or ntp.check_clock(args.ntp_server)
    mon = monitor.UnitMonitor()
    client = monitor.watch(cfg, mon)
    started = time.monotonic()
    try:
        if wait_for_unit:
            print("Waiting for the unit's first status message (it sends one every 10 s). Ctrl+C to stop waiting.")
            while not mon.status_seen.wait(1):
                pass
            if open_url:
                print(f"Opening {open_url}")
                print("In the dashboard, enter the MQTT password once in Settings (it is kept for that tab only).")
                webbrowser.open(open_url)
                time.sleep(1)
        elif not live:
            print(f"Listening for {STATUS_LISTEN_S} s ...")
            time.sleep(STATUS_LISTEN_S)
        while True:
            now = time.monotonic()
            screen = render(
                records, mon, client.is_connected(), clock, cfg.host, cfg.port, now, now - started
            )
            if not live:
                print(screen)
                return 0
            os.system("cls" if os.name == "nt" else "clear")
            print(screen)
            print("\nCtrl+C closes this screen. Everything keeps running. Stop it with: invigil stop")
            time.sleep(REFRESH_S)
    except KeyboardInterrupt:
        print("\nLeft running. Stop everything with: invigil stop")
        return 0
    finally:
        monitor.close(client)


def stop_all(records: list[dict]) -> None:
    for record in reversed(records):
        print(f"{record['name']} (PID {record['pid']}): {procs.stop(record)}")
    procs.save_run([r for r in records if procs.is_running(r)])


def cmd_stop(args) -> int:
    records = procs.load_run()
    if not records:
        print("Nothing to stop: the launcher has not started anything.")
        return 0
    stop_all(records)
    return 0


def cmd_status(args) -> int:
    return show_status(args, procs.load_run(), live=False, wait_for_unit=False)


def cmd_calibrate(args) -> int:
    try:
        return run_calibration(args)
    except EOFError:
        print("\nInput ended. Progress so far is saved. Run calibrate again to continue.")
        return 1


def run_calibration(args) -> int:
    progress, path = calibrate.setup(args)
    if not progress.remaining():
        print(calibrate.results_table(progress))
        print(f"\nAll steps are done. To record this device again, delete {path}")
        return 0
    record, close = calibrate.mqtt_recorder(load_config())
    try:
        calibrate.run(progress, path, record, seconds=args.seconds)
    except KeyboardInterrupt:
        print("\nStopped. The step in progress is not saved. Run calibrate again to continue.")
    finally:
        close()
    return 0


SHORTCUT_PS = (
    "$d = [Environment]::GetFolderPath('Desktop'); "
    "$p = Join-Path $d 'Invigil.lnk'; "
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p); "
    "$s.TargetPath = $env:INVIGIL_BAT; $s.Arguments = 'start'; "
    "$s.WorkingDirectory = $env:INVIGIL_ROOT; "
    "$s.Description = 'Start the Invigil laptop side'; $s.Save(); $p"
)


def cmd_shortcut(args) -> int:
    if sys.platform != "win32":
        print("The desktop shortcut is for Windows only.")
        return 1
    env = dict(os.environ, INVIGIL_BAT=str(ROOT / "invigil.bat"), INVIGIL_ROOT=str(ROOT))
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", SHORTCUT_PS], env=env, capture_output=True, text=True
    )
    if out.returncode != 0:
        print(out.stderr.strip())
        return 1
    print(f"Created {out.stdout.strip()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="invigil", description="Run the Invigil laptop side.")
    parser.add_argument("--ntp-server", default=ntp.DEFAULT_SERVER, help="server for the clock check")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="start the broker, the logger and the dashboard")
    p.add_argument("--session", help="logger session name (default: live-<time>)")
    p.add_argument("--port", type=int, default=dashboard.PORT, help="dashboard port (default: 8080)")
    p.set_defaults(func=cmd_start)

    sub.add_parser("stop", help="stop what start started").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="show the status screen").set_defaults(func=cmd_status)

    p = sub.add_parser("calibrate", help="guided RSSI calibration from 0.5 to 3.5 m")
    p.add_argument("--type", choices=calibrate.TYPES)
    p.add_argument("--name", help="device name, for example 'earpiece A'")
    p.add_argument("--state", help="device state, for example 'streaming'")
    p.add_argument("--position", choices=calibrate.POSITIONS)
    p.add_argument("--seconds", type=int, default=calibrate.SECONDS, help="recording time per step")
    p.set_defaults(func=cmd_calibrate)

    sub.add_parser("shortcut", help="put an Invigil shortcut on the Windows desktop").set_defaults(func=cmd_shortcut)

    args = parser.parse_args(argv)
    os.chdir(ROOT)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
