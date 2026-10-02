import random

from server import contract
from server.fake_publisher import WIFI_CHANNELS, band_of, default_devices, simulate_window

T0 = 1_790_000_000_000


def run_windows(n, seed=1):
    rng = random.Random(seed)
    devices = default_devices("test-salt", rng)
    msgs = []
    for i in range(n):
        for node in contract.NODE_IDS:
            t0 = T0 + i * 1000
            msgs.append((t0, t0 + 800, simulate_window(node, t0, t0 + 800, devices, 20, rng)))
    return devices, msgs


def test_every_message_follows_the_contract():
    _, windows = run_windows(30)
    for t0, t1, msgs in windows:
        for kind, payload in msgs:
            contract.validate(kind, payload, payload["node"])
            assert t0 <= payload["ts"] <= t1  # nothing from the send window


def test_one_spectrum_message_per_window():
    _, windows = run_windows(5)
    for _, _, msgs in windows:
        assert [k for k, _ in msgs].count("spectrum") == 1


def test_only_advertising_devices_show_up_in_ble():
    devices, windows = run_windows(30)
    advertising = {d.addr for d in devices if d.adv_interval_ms}
    silent = {d.addr for d in devices if not d.adv_interval_ms}
    seen = {p["addr"] for _, _, msgs in windows for k, p in msgs if k == "ble"}
    assert seen == advertising
    assert not seen & silent


def test_spectrum_shows_wifi_block_and_bluetooth_hopping():
    _, windows = run_windows(30)
    totals = [0] * contract.NUM_CHANNELS
    for _, _, msgs in windows:
        for kind, p in msgs:
            if kind == "spectrum":
                totals = [a + b for a, b in zip(totals, p["hits"])]
    wifi = sum(totals[c] for c in WIFI_CHANNELS) / len(WIFI_CHANNELS)
    hop = sum(totals[c] for c in range(2, 27)) / 25
    above_bt = sum(totals[c] for c in range(81, 126)) / 45  # no Bluetooth up here
    assert wifi > hop > above_bt


def test_band_edges_match_the_data_protocol():
    assert [band_of(d) for d in (0.5, 0.99, 1.0, 1.5, 2.0, 3.0, 3.49)] == [
        "near", "near", "mid", "mid", "far", "far", "far"]
    assert band_of(3.5) == "out of range"


def test_every_device_has_a_type_and_a_band():
    devices = default_devices("test-salt", random.Random(1))
    assert {d.kind for d in devices} == {"phone", "earpiece", "smartwatch", "allowed"}
    assert {d.band for d in devices} == {"near", "mid", "far"}
