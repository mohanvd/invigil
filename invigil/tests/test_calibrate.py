import json
from argparse import Namespace

import pytest

from invigil import calibrate
from ml.features import load_meta
from server.logger import CsvSink, Recorder

TS = 1_793_019_264_000
DEVICE = "a91f03c2d4e8"
BACKGROUND = "0123456789ab"
# What the device "sends" at each distance in these tests.
RSSI_AT = {0.5: -48, 1.0: -55, 1.5: -60, 2.0: -64, 2.5: -68, 3.0: -71, 3.5: -74}


def ble(addr, rssi, i):
    msg = {"ts": TS + i * 100, "node": "N1", "addr": addr, "rssi": rssi, "mfr": "0x004C"}
    return json.dumps(msg).encode()


class FakeUnit:
    """Stands in for the unit: record() writes readings through the real Recorder."""

    def __init__(self, device=DEVICE):
        self.device = device
        self.recorded = []

    def record(self, folder, seconds):
        distance = float(folder.name.split("-")[-1].rstrip("m"))
        rec = Recorder(CsvSink(folder))
        for i in range(20):
            rec.handle("invigil/node/N1/ble", ble(self.device, RSSI_AT[distance] - i % 3, i), TS)
            rec.handle("invigil/node/N1/ble", ble(BACKGROUND, -80, i), TS)
        rec.close()
        self.recorded.append(distance)


def answers(*items):
    queue = list(items)
    return lambda prompt: queue.pop(0)


@pytest.fixture
def progress(tmp_path):
    p = calibrate.Progress("earpiece", "earpiece A", "streaming", "desk")
    path = tmp_path / "progress.json"
    p.save(path)
    return p, path


def test_bands_follow_the_data_protocol():
    assert [calibrate.band_for(d) for d in calibrate.DISTANCES] == [
        "near", "mid", "mid", "mid", "far", "far", "far",
    ]


def test_session_names_are_valid_logger_sessions():
    assert calibrate.slug("Earpiece A (left)") == "earpiece-a-left"
    assert calibrate.session_name("earpiece", "earpiece-a", 0.5) == "calib-earpiece-earpiece-a-0.5m"
    assert calibrate.session_name("phone", "phone-b", 3.0) == "calib-phone-phone-b-3m"
    with pytest.raises(ValueError):
        calibrate.slug("  !!  ")


def test_full_run_labels_every_step_and_prints_medians(tmp_path, progress):
    p, path = progress
    unit = FakeUnit()
    said = []
    # Enter at each of 7 steps, plus Enter to accept the suggested hash at the first.
    calibrate.run(p, path, unit.record, answers("", "", *[""] * 6), said.append, out_base=tmp_path)

    assert unit.recorded == list(calibrate.DISTANCES)
    assert p.devices == [DEVICE]
    for d in calibrate.DISTANCES:
        folder = tmp_path / p.steps[calibrate.step_key(d)].split("\\")[-1].split("/")[-1]
        meta = load_meta(folder)  # the same check training uses
        labels = meta["devices"][DEVICE]
        assert labels["type"] == "earpiece" and labels["band"] == calibrate.band_for(d)
        assert labels["model"] == "earpiece A" and labels["distance_m"] == d
        assert meta["kind"] == "calibration"
        assert BACKGROUND not in meta["devices"]

    rows = {line.split()[0]: line.split()[1:] for line in said[-1].strip().splitlines()[1:]}
    assert rows["0.5m"] == ["near", "20", "-49.0", "dBm"]
    assert rows["2m"] == ["mid", "20", "-65.0", "dBm"]
    assert rows["3.5m"] == ["far", "20", "-75.0", "dBm"]


def test_progress_is_saved_and_a_stopped_run_resumes(tmp_path, progress):
    p, path = progress
    unit = FakeUnit()
    # Two steps, then q at the third.
    calibrate.run(p, path, unit.record, answers("", "", "", "q"), lambda s: None, out_base=tmp_path)
    assert unit.recorded == [0.5, 1.0]

    resumed = calibrate.Progress.load(path)
    assert resumed.devices == [DEVICE]
    assert resumed.remaining() == [1.5, 2.0, 2.5, 3.0, 3.5]
    unit.recorded.clear()
    calibrate.run(resumed, path, unit.record, answers(*[""] * 5), lambda s: None, out_base=tmp_path)
    assert unit.recorded == [1.5, 2.0, 2.5, 3.0, 3.5]
    assert calibrate.Progress.load(path).remaining() == []


def test_a_half_recorded_step_is_moved_aside_not_mixed_in(tmp_path, progress):
    p, path = progress
    p.distances = [0.5]
    from server.logger import session_dir

    stale = session_dir(tmp_path, calibrate.session_name("earpiece", "earpiece-a", 0.5))
    stale.mkdir(parents=True)
    (stale / "ble.csv").write_text("left over from a stopped step\n")
    said = []
    calibrate.run(p, path, FakeUnit().record, answers("", ""), said.append, out_base=tmp_path)

    moved = [f for f in tmp_path.iterdir() if "-incomplete-" in f.name]
    assert len(moved) == 1 and (moved[0] / "ble.csv").read_text().startswith("left over")
    assert "left over" not in (stale / "ble.csv").read_text()


def test_a_rotated_address_is_asked_for(tmp_path, progress):
    p, path = progress
    p.distances = [0.5, 1.0]
    p.devices = ["ffffffffffff"]  # an address the unit no longer uses
    said = []
    # Step 1: not heard, user types the new hash. Step 2: found again.
    calibrate.run(p, path, FakeUnit().record, answers("", DEVICE, ""), said.append, out_base=tmp_path)
    assert DEVICE in p.devices
    assert any("may have changed address" in s for s in said)


def test_a_step_with_no_readings_is_repeated(tmp_path, progress):
    p, path = progress
    p.distances = [0.5]
    calls = []

    def flaky(folder, seconds):
        calls.append(folder)
        if len(calls) > 1:
            FakeUnit().record(folder, seconds)

    said = []
    calibrate.run(p, path, flaky, answers("", "", ""), said.append, out_base=tmp_path)
    assert len(calls) == 2
    assert any("No BLE readings" in s for s in said)
    assert p.remaining() == []


def test_setup_asks_for_what_is_missing_and_finds_saved_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(calibrate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(calibrate.Progress, "path_for", staticmethod(lambda t, n, base=tmp_path: base / f"{t}-{calibrate.slug(n)}.json"))
    args = Namespace(type=None, name=None, state=None, position=None)
    p, path = calibrate.setup(args, answers("watch", "smartwatch", "Watch B", "on wrist", "desk"))
    assert (p.type, p.name, p.state, p.position) == ("smartwatch", "Watch B", "on wrist", "desk")
    assert path.exists()

    again, _ = calibrate.setup(Namespace(type="smartwatch", name="Watch B", state=None, position=None))
    assert again.state == "on wrist"
