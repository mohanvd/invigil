import json

from invigil import dashboard, monitor, ntp
from invigil.__main__ import fmt_rate, fmt_uptime, render

TS = 1_793_019_264_000


def status(uptime=3725, rssi=-43):
    return json.dumps({"ts": TS, "node": "N1", "uptime_s": uptime, "wifi_rssi": rssi, "fw": "0.1.0"}).encode()


def ble():
    return json.dumps({"ts": TS, "node": "N1", "addr": "a91f03c2d4e8", "rssi": -60, "mfr": None}).encode()


def test_rates_count_the_last_window_only():
    mon = monitor.UnitMonitor(window_s=10)
    for i in range(50):
        mon.handle("invigil/node/N1/ble", ble(), now=100 + i * 0.2)  # 5 per s for 10 s
    mon.handle("invigil/node/N1/ble", ble(), now=50)  # long ago
    view = mon.view("N1", now=110)
    assert view.rates["ble"] == 5.0
    assert view.rates["spectrum"] == 0.0


def test_rates_use_the_time_listened_when_shorter_than_the_window():
    mon = monitor.UnitMonitor(window_s=10)
    for i in range(10):
        mon.handle("invigil/node/N1/ble", ble(), now=100 + i * 0.2)
    assert mon.view("N1", now=102, listened_s=2).rates["ble"] == 5.0


def test_online_follows_the_status_messages():
    mon = monitor.UnitMonitor()
    assert not mon.view("N1", now=0).online
    assert mon.handle("invigil/node/N1/status", status(), now=100)
    assert mon.status_seen.is_set()
    assert mon.view("N1", now=120).online
    view = mon.view("N1", now=131)
    assert not view.online and view.status_age_s == 31
    assert view.last_status["wifi_rssi"] == -43


def test_messages_that_break_the_contract_are_only_counted():
    mon = monitor.UnitMonitor()
    raw_mac = json.dumps({"ts": TS, "node": "N1", "addr": "A9:1F:03:C2:D4:E8", "rssi": -60, "mfr": None})
    assert not mon.handle("invigil/node/N1/ble", raw_mac.encode(), now=1)
    assert not mon.handle("invigil/node/N1/status", b"{not json", now=1)
    assert mon.rejected == 2
    assert mon.view("N1", now=1).rates["ble"] == 0


def test_status_screen_shows_every_line():
    mon = monitor.UnitMonitor()
    mon.handle("invigil/node/N1/status", status(), now=100)
    records = []  # nothing started by the launcher
    clock = ntp.ClockCheck("pool.ntp.org", 1450.0)
    screen = render(records, mon, True, clock, "localhost", 1883, now=104)
    assert "Broker       running at localhost:1883 (not started by the launcher)" in screen
    assert "Logger       not running" in screen
    assert "Unit N1      online" in screen
    assert "uptime 1h 02m, Wi-Fi RSSI -43 dBm, fw 0.1.0, 4 s ago" in screen
    assert "rejected 0" in screen
    assert "1450 ms behind pool.ntp.org" in screen and "WARNING" in screen


def test_status_screen_when_nothing_is_reachable():
    mon = monitor.UnitMonitor()
    mon.connect_error = "no answer from localhost:1883"
    screen = render([], mon, False, ntp.ClockCheck("pool.ntp.org", None, "timed out"), "localhost", 1883, now=0)
    assert "NOT reachable at localhost:1883 no answer" in screen
    assert "no status message yet" in screen
    assert "offset unknown" in screen


def test_number_formats():
    assert fmt_uptime(59) == "0m 59s"
    assert fmt_uptime(3725) == "1h 02m"
    assert fmt_rate(46.23) == "46.2/s"
    assert fmt_rate(0.0) == "0.0/s"
    assert fmt_rate(0.05) == "1 per 20 s"


def test_live_url_opens_live_mode_without_a_password():
    url = dashboard.live_url(8080, "ws://localhost:9001", "invigil")
    assert url.startswith("http://127.0.0.1:8080/?")
    assert "source=live" in url and "broker=ws%3A%2F%2Flocalhost%3A9001" in url and "user=invigil" in url
    assert url.endswith("#/live")
    assert "password" not in url


def test_dashboard_rebuilds_when_a_source_is_newer(tmp_path):
    import os

    (tmp_path / "src").mkdir()
    src = tmp_path / "src" / "main.tsx"
    src.write_text("x")
    assert dashboard.needs_build(tmp_path)  # never built
    (tmp_path / "dist").mkdir()
    index = tmp_path / "dist" / "index.html"
    index.write_text("<html>")
    os.utime(src, (1000, 1000))
    os.utime(index, (2000, 2000))
    assert not dashboard.needs_build(tmp_path)
    os.utime(src, (3000, 3000))
    assert dashboard.needs_build(tmp_path)


def test_local_builds_are_never_demo_only(monkeypatch):
    monkeypatch.setenv("VITE_DEMO_ONLY", "true")
    assert "VITE_DEMO_ONLY" not in dashboard.build_env()


def test_dashboard_is_served_on_localhost_only():
    cmd = dashboard.serve_cmd(8080)
    assert cmd[cmd.index("--bind") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--directory") + 1] == str(dashboard.DIST)
