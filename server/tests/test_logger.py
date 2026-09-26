import csv
import json

from server.logger import COLUMNS, CsvSink, Recorder

TS = 1727340000123


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def make_recorder(tmp_path):
    return Recorder(CsvSink(tmp_path / "session"))


def test_valid_ble_is_written_with_rx_ts(tmp_path):
    rec = make_recorder(tmp_path)
    msg = {"ts": TS, "node": "N2", "addr": "a91f03c2d4e8", "rssi": -58, "mfr": "0x004C"}
    assert rec.handle("invigil/node/N2/ble", json.dumps(msg).encode(), TS + 400)
    rec.close()

    rows = read_csv(tmp_path / "session" / "ble.csv")
    assert rows[0] == COLUMNS["ble"]
    assert rows[1] == [str(TS + 400), str(TS), "N2", "a91f03c2d4e8", "-58", "0x004C"]


def test_null_mfr_is_an_empty_cell(tmp_path):
    rec = make_recorder(tmp_path)
    msg = {"ts": TS, "node": "N1", "addr": "a91f03c2d4e8", "rssi": -70, "mfr": None}
    assert rec.handle("invigil/node/N1/ble", json.dumps(msg).encode(), TS)
    rec.close()
    assert read_csv(tmp_path / "session" / "ble.csv")[1][-1] == ""


def test_spectrum_gets_one_column_per_channel(tmp_path):
    rec = make_recorder(tmp_path)
    hits = list(range(126))
    msg = {"ts": TS, "node": "N3", "sweeps": 200, "hits": hits}
    assert rec.handle("invigil/node/N3/spectrum", json.dumps(msg).encode(), TS)
    rec.close()

    header, row = read_csv(tmp_path / "session" / "spectrum.csv")
    assert len(header) == 4 + 126
    assert header[4] == "ch000" and header[-1] == "ch125"
    assert [int(x) for x in row[4:]] == hits


def test_rejected_messages_never_reach_disk(tmp_path):
    rec = make_recorder(tmp_path)
    raw_mac = "A9:1F:03:C2:D4:E8"
    bad = {"ts": TS, "node": "N1", "addr": raw_mac, "rssi": -58, "mfr": "0x004C"}
    assert not rec.handle("invigil/node/N1/ble", json.dumps(bad).encode(), TS)
    assert not rec.handle("invigil/node/N1/ble", b"{not json", TS)
    assert not rec.handle("invigil/node/N9/ble", b"{}", TS)
    rec.close()

    assert rec.total == 0
    assert "rejected 3" in rec.report()
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert written == []


def test_report_counts_and_resets(tmp_path):
    rec = make_recorder(tmp_path)
    msg = {"ts": TS, "node": "N1", "uptime_s": 10, "wifi_rssi": -50, "fw": "0.1.0"}
    rec.handle("invigil/node/N1/status", json.dumps(msg).encode(), TS + 30)
    rec.handle("invigil/node/N1/status", b"garbage", TS)

    line = rec.report()
    assert "N1: 1 status" in line
    assert "N2: silent" in line
    assert "p50 30 ms" in line
    assert "rejected 1" in line
    assert "rejected 0" in rec.report()
    rec.close()


def test_reopening_a_session_appends_without_a_second_header(tmp_path):
    msg = {"ts": TS, "node": "N1", "uptime_s": 10, "wifi_rssi": -50, "fw": "0.1.0"}
    for _ in range(2):
        rec = make_recorder(tmp_path)
        rec.handle("invigil/node/N1/status", json.dumps(msg).encode(), TS)
        rec.close()
    rows = read_csv(tmp_path / "session" / "status.csv")
    assert len(rows) == 3 and rows[0] == COLUMNS["status"]
