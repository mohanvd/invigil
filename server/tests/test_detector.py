import numpy as np
import pytest
from sklearn.dummy import DummyClassifier

from ml.features import BAND_FEATURE_COLS, FEATURE_COLS
from server import contract
from server.config import load_config
from server.contract import ContractError, validate
from server.detector import Detector

TS = 1727340000000
NEAR = "a91f03c2d4e8"
WEAK = "0f5e2b7a91c4"


def detection(**changes):
    d = {"ts": TS, "node": "N1", "addr": NEAR, "type": "earpiece", "type_conf": 0.91,
         "band": "near", "band_conf": 0.84, "rssi": -52}
    d.update(changes)
    return d


def dummy(features, classes, pick):
    X = np.zeros((len(classes), len(features)))
    model = DummyClassifier(strategy="constant", constant=pick).fit(X, classes)
    return {"model": model, "features": features, "classes": list(model.classes_)}


@pytest.fixture
def models():
    return {
        "type": dummy(FEATURE_COLS, ["phone", "earpiece"], "phone"),
        "band": dummy(BAND_FEATURE_COLS, ["near", "not_near"], "near"),
    }


def ble_msg(addr, rssi, start, n, step=300, mfr="0x004C"):
    readings = [{"ts": start + i * step, "addr": addr, "rssi": rssi, "mfr": mfr} for i in range(n)]
    return {"ts": start + n * step, "node": "N1", "readings": readings}


def test_contract_accepts_a_detection():
    assert validate("detection", detection(), "N1")
    assert validate("detection", detection(addr=None, rssi=None, band="not_near", type_conf=1))
    assert contract.topic("N1", "detection") == "invigil/node/N1/detection"


@pytest.mark.parametrize("bad", [
    {"band": "mid"}, {"band": "far"}, {"type": "tablet"}, {"type_conf": 1.2}, {"band_conf": True},
    {"addr": "AA:BB:CC:DD:EE:FF"}, {"rssi": 5}, {"rssi": -60.5},
])
def test_contract_rejects_bad_detections(bad):
    with pytest.raises(ContractError):
        validate("detection", detection(**bad))


def test_detector_reports_strong_devices_and_drops_weak_ones(models):
    det = Detector(models, min_rssi=-85)
    det.add("ble", ble_msg(NEAR, -60, TS, 10))
    det.add("ble", ble_msg(WEAK, -95, TS, 10))
    out = det.decide(TS + 5000)
    assert [d["addr"] for d in out] == [NEAR]
    d = out[0]
    assert d["type"] == "phone" and d["band"] == "near" and d["rssi"] == -60
    assert d["ts"] == TS + 9 * 300  # the last reading used
    validate("detection", d, "N1")


def test_detector_needs_enough_advertisements_in_the_window(models):
    det = Detector(models)
    det.add("ble", ble_msg(NEAR, -60, TS, 1))
    assert det.decide(TS + 5000) == []
    # readings older than the 5 s window no longer count
    det.add("ble", ble_msg(NEAR, -60, TS + 100, 3))
    assert det.decide(TS + 20_000) == []


def test_whitelisted_device_is_reported_as_allowed(models):
    det = Detector(models, allowed=(NEAR,))
    det.add("ble", ble_msg(NEAR, -60, TS, 10))
    (d,) = det.decide(TS + 5000)
    assert d["type"] == "allowed" and d["type_conf"] == 1.0
    assert d["band"] == "near"


def test_config_reads_whitelist_and_rejects_raw_addresses(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(f'[whitelist]\nallowed = ["{NEAR}"]\n[detector]\nmin_rssi = -80\n')
    cfg = load_config(path)
    assert cfg.allowed == (NEAR,) and cfg.min_rssi == -80

    path.write_text('[whitelist]\nallowed = ["AA:BB:CC:DD:EE:FF"]\n')
    with pytest.raises(ValueError):
        load_config(path)
