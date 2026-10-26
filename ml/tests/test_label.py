import json

from ml.label import device_labels, write_session_json


def test_template_keeps_the_question_marks_training_refuses():
    assert device_labels() == {"type": "?", "band": "?", "model": "", "state": "", "position": ""}


def test_write_session_json_never_overwrites(tmp_path):
    first = write_session_json(tmp_path, {"a91f03c2d4e8": device_labels("phone", "near")}, kind="calibration")
    meta = json.loads(first.read_text())
    assert meta["name"] == tmp_path.name
    assert meta["kind"] == "calibration"
    assert meta["devices"]["a91f03c2d4e8"]["type"] == "phone"
    assert list(meta) == ["name", "notes", "kind", "devices"]

    assert write_session_json(tmp_path, {"0123456789ab": device_labels()}) is None
    assert json.loads(first.read_text()) == meta
