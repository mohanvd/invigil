import csv
import json

from server.logger import COLUMNS, CsvSink, Recorder

TS = 1727340000123


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def make_recorder(tmp_path):
    return Recorder(CsvSink(tmp_path / "session"))


def ble(*readings, ts=TS + 900):
    return {"ts": ts, "node": "N1", "readings": list(readings)}


def reading(ts=TS, addr="a91f03c2d4e8", rssi=-58, mfr="0x004C"):
    return {"ts": ts, "addr": addr, "rssi": rssi, "mfr": mfr}


def test_ble_csv_columns_are_unchanged():
    assert COLUMNS["ble"] == ["rx_ts", "ts", "node", "addr", "rssi", "mfr"]


def test_valid_ble_is_written_with_rx_ts(tmp_path):
    rec = make_recorder(tmp_path)
    assert rec.handle("invigil/node/N1/ble", json.dumps(ble(reading())).encode(), TS + 400)
    rec.close()

    rows = read_csv(tmp_path / "session" / "ble.csv")
    assert rows[0] == COLUMNS["ble"]
    assert rows[1] == [str(TS + 400), str(TS), "N1", "a91f03c2d4e8", "-58", "0x004C"]


def test_each_reading_gets_its_own_row_and_ts(tmp_path):
    rec = make_recorder(tmp_path)
    msg = ble(reading(), reading(ts=TS + 250, addr="0f5e2b7a91c4", rssi=-81, mfr=None))
    assert rec.handle("invigil/node/N1/ble", json.dumps(msg).encode(), TS + 1000)
    rec.close()

    rows = read_csv(tmp_path / "session" / "ble.csv")
    assert rows[1:] == [
        [str(TS + 1000), str(TS), "N1", "a91f03c2d4e8", "-58", "0x004C"],
        [str(TS + 1000), str(TS + 250), "N1", "0f5e2b7a91c4", "-81", ""],
    ]
    assert rec.total == 2
    line = rec.report()
    assert "N1: 2 ble" in line
    assert "p50 875 ms" in line  # latencies 1000 and 750, from each reading's own ts


def test_null_mfr_is_an_empty_cell(tmp_path):
    rec = make_recorder(tmp_path)
    assert rec.handle("invigil/node/N1/ble", json.dumps(ble(reading(rssi=-70, mfr=None))).encode(), TS)
    rec.close()
    assert read_csv(tmp_path / "session" / "ble.csv")[1][-1] == ""


def test_spectrum_gets_one_column_per_channel(tmp_path):
    rec = make_recorder(tmp_path)
    hits = list(range(126))
    msg = {"ts": TS, "node": "N1", "sweeps": 200, "hits": hits}
    assert rec.handle("invigil/node/N1/spectrum", json.dumps(msg).encode(), TS)
    rec.close()

    header, row = read_csv(tmp_path / "session" / "spectrum.csv")
    assert len(header) == 4 + 126
    assert header[4] == "ch000" and header[-1] == "ch125"
    assert [int(x) for x in row[4:]] == hits


def test_rejected_messages_never_reach_disk(tmp_path):
    rec = make_recorder(tmp_path)
    raw_mac = "A9:1F:03:C2:D4:E8"
    # One raw address in an otherwise good message rejects the whole message.
    bad = ble(reading(), reading(addr=raw_mac))
    assert not rec.handle("invigil/node/N1/ble", json.dumps(bad).encode(), TS)
    old_shape = {"ts": TS, "node": "N1", "addr": "a91f03c2d4e8", "rssi": -58, "mfr": "0x004C"}
    assert not rec.handle("invigil/node/N1/ble", json.dumps(old_shape).encode(), TS)
    assert not rec.handle("invigil/node/N1/ble", b"{not json", TS)
    assert not rec.handle("invigil/node/N9/ble", b"{}", TS)
    rec.close()

    assert rec.total == 0
    assert "rejected 4" in rec.report()
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert written == []


def test_report_counts_and_resets(tmp_path):
    rec = make_recorder(tmp_path)
    msg = {"ts": TS, "node": "N1", "uptime_s": 10, "wifi_rssi": -50, "fw": "0.1.0"}
    rec.handle("invigil/node/N1/status", json.dumps(msg).encode(), TS + 30)
    rec.handle("invigil/node/N1/status", b"garbage", TS)

    line = rec.report()
    assert "N1: 1 status" in line
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
