import json

import joblib
import pytest

from ml import features, label, synth, train


@pytest.fixture(scope="module")
def sessions(tmp_path_factory):
    out = tmp_path_factory.mktemp("synthetic")
    synth.generate(out, repeats=2, seconds=30)
    return out


def test_synthetic_sessions_are_labeled(sessions):
    found = features.find_sessions(sessions)
    assert len(found) == 4 * 3 * 2
    df = features.dataset(sessions)
    assert set(df["type"]) == set(features.TYPES)
    assert set(df["band"]) == set(features.BANDS)
    # background devices are dropped: one labeled address per session
    assert (df.groupby("session")["addr"].nunique() == 1).all()


def test_folds_never_share_a_session(sessions):
    df = features.dataset(sessions)
    for train_idx, test_idx in train.folds(df["session"]):
        assert not set(df["session"].iloc[train_idx]) & set(df["session"].iloc[test_idx])


def test_one_session_is_not_enough(sessions):
    df = features.dataset(sessions)
    one = df[df["session"] == df["session"].iloc[0]]
    with pytest.raises(SystemExit):
        train.folds(one["session"])


def test_train_writes_report_and_models(sessions, tmp_path):
    results, models = tmp_path / "results", tmp_path / "models"
    train.main(["--data", str(sessions), "--name", "t", "--results", str(results), "--models", str(models)])

    report = next(results.glob("*-t")) / "report.md"
    text = report.read_text(encoding="utf-8")
    assert "## type" in text and "## band" in text
    assert "Banned devices flagged as banned" in text
    for target in ("type", "band"):
        saved = joblib.load(models / f"{target}.joblib")
        assert saved["features"] == features.FEATURE_COLS
        assert len(saved["model"].predict([[0.0] * len(features.FEATURE_COLS)])) == 1


def test_label_writes_template_with_strongest_device(sessions, tmp_path):
    src = features.find_sessions(sessions)[0]
    folder = tmp_path / "rec"
    folder.mkdir()
    (folder / "ble.csv").write_bytes((src / "ble.csv").read_bytes())

    label.main([str(folder)])
    meta = json.loads((folder / "session.json").read_text())
    real = json.loads((src / "session.json").read_text())["devices"]
    assert list(meta["devices"]) == list(real)  # the test device is the strongest
    assert meta["devices"][next(iter(real))]["type"] == "?"
    with pytest.raises(features.SessionError):
        features.session_features(folder)  # "?" is refused until filled in
