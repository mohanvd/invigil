import csv
import json

import numpy as np
import pandas as pd
import pytest

from ml import features as F
from server.logger import COLUMNS

TS = 1_790_000_000_000
TARGET = "a91f03c2d4e8"
OTHER = "0123456789ab"


def spec_frame(active_channels, sweeps=50, hits=50):
    row = {"rx_ts": TS, "ts": TS, "node": "N1", "sweeps": sweeps}
    row.update({c: (hits if i in active_channels else 0) for i, c in enumerate(F.CHANNEL_COLS)})
    return pd.DataFrame([row])


def test_wifi_block_is_one_long_run():
    f = F.spectrum_features(spec_frame(range(27, 48)))
    assert f["spec_active"] == 21
    assert f["spec_runs"] == 1
    assert f["spec_longest_run"] == 21
    assert f["spec_scattered"] == 0


def test_hopping_is_many_scattered_hits():
    f = F.spectrum_features(spec_frame(range(2, 81, 3)))
    assert f["spec_runs"] == f["spec_active"] == 27
    assert f["spec_scattered"] == 27
    assert f["spec_longest_run"] == 1


def test_spectrum_threshold_uses_share_of_sweeps():
    # 1 hit in 100 sweeps is 1%, below the 2% ACTIVE_FRAC
    assert F.spectrum_features(spec_frame([10], sweeps=100, hits=1))["spec_active"] == 0
    assert F.spectrum_features(spec_frame([10], sweeps=100, hits=5))["spec_active"] == 1


def test_no_sweeps_gives_missing_values():
    empty = pd.DataFrame(columns=["rx_ts", "ts", "node", "sweeps", *F.CHANNEL_COLS])
    assert set(F.spectrum_features(empty).values()) == {F.MISSING}


def test_adv_interval_is_robust_to_a_missed_packet():
    ts = np.array([0, 100, 200, 400, 500])  # the ad at 300 was missed
    f = F.ble_features(ts, np.array([-60.0] * 5), "0x004C")
    assert f["adv_interval_ms"] == 100
    assert f["n_adv"] == 5


def test_single_advertisement_has_no_interval():
    f = F.ble_features(np.array([0]), np.array([-60.0]), "")
    assert f["adv_interval_ms"] == F.MISSING


@pytest.mark.parametrize("mfr,col", [("0x004C", "mfr_apple"), ("", "mfr_none"), ("0x1234", "mfr_other")])
def test_mfr_onehot(mfr, col):
    out = F.mfr_onehot(mfr)
    assert out[col] == 1.0
    assert sum(out.values()) == 1.0


def write_session(folder, devices, ble_rows, spec_rows=()):
    folder.mkdir(parents=True)
    for kind, rows in (("ble", ble_rows), ("spectrum", spec_rows)):
        with open(folder / f"{kind}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS[kind])
            w.writerows(rows)
    if devices is not None:
        (folder / "session.json").write_text(json.dumps({"devices": devices}))
    return folder


def ble_rows(addr, mfr, n, every_ms=200, rssi=-60):
    return [[TS + i * every_ms, TS + i * every_ms, "N1", addr, rssi, mfr] for i in range(n)]


def test_session_keeps_only_labeled_devices(tmp_path):
    rows = ble_rows(TARGET, "0x004C", 50) + ble_rows(OTHER, "", 50, rssi=-85)
    s = write_session(tmp_path / "s1", {TARGET: {"type": "earpiece", "band": "near"}}, rows)
    df = F.session_features(s)
    assert set(df["addr"]) == {TARGET}
    assert set(df["type"]) == {"earpiece"} and set(df["band"]) == {"near"}
    # 50 ads x 200 ms = ~10 s of data, 5 s windows every 1 s
    assert len(df) == 5
    assert df["adv_interval_ms"].eq(200).all()
    assert df["mfr_apple"].eq(1).all()


def test_empty_mfr_cell_reads_as_none(tmp_path):
    s = write_session(tmp_path / "s1", {OTHER: {"type": "phone", "band": "far"}}, ble_rows(OTHER, "", 30))
    df = F.session_features(s)
    assert df["mfr_none"].eq(1).all()


def test_spectrum_is_joined_by_time(tmp_path):
    hop = [TS, TS, "N1", 50] + [50 if 2 <= c <= 80 and c % 3 == 0 else 0 for c in range(126)]
    s = write_session(tmp_path / "s1", {TARGET: {"type": "earpiece", "band": "near"}}, ble_rows(TARGET, "0x004C", 60), [hop])
    df = F.session_features(s)  # ads span 11.8 s, so 5 s windows start at 0..6 s
    assert len(df) == 7
    assert df.iloc[0]["spec_scattered"] > 20  # first window contains the sweep
    assert df.iloc[-1]["spec_sweeps"] == F.MISSING  # later windows do not


@pytest.mark.parametrize("bad", [{"type": "?", "band": "near"}, {"type": "phone", "band": "?"}, {"type": "tablet", "band": "mid"}])
def test_unfinished_labels_are_refused(tmp_path, bad):
    s = write_session(tmp_path / "s1", {TARGET: bad}, ble_rows(TARGET, "0x004C", 30))
    with pytest.raises(F.SessionError):
        F.session_features(s)


def test_missing_session_json_says_what_to_run(tmp_path):
    s = write_session(tmp_path / "s1", None, ble_rows(TARGET, "0x004C", 30))
    with pytest.raises(F.SessionError, match="ml.label"):
        F.session_features(s)
