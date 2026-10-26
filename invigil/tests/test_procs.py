import sys
import time

from invigil import procs

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


def test_spawn_records_a_process_that_stop_can_end(tmp_path):
    record = procs.spawn("sleeper", SLEEPER, log_dir=tmp_path, extra="kept")
    try:
        assert record["started"] is not None
        assert record["extra"] == "kept"
        assert procs.is_running(record)
    finally:
        result = procs.stop(record)
    assert result == "stopped"
    assert not procs.is_running(record)
    assert procs.stop(record) == "not running"


def test_a_reused_pid_is_never_touched(tmp_path):
    record = procs.spawn("sleeper", SLEEPER, log_dir=tmp_path)
    try:
        # Same PID, but a different start time: it would be another program.
        impostor = dict(record, started=record["started"] + 1)
        assert not procs.is_running(impostor)
        assert procs.stop(impostor) == "not running"
        assert procs.is_running(record)
    finally:
        procs.stop(record)


def test_missing_start_time_is_treated_as_not_running():
    assert not procs.is_running({"pid": 1, "started": None})


def test_run_file_round_trip(tmp_path):
    path = tmp_path / "run.json"
    assert procs.load_run(path) == []
    records = [{"name": "logger", "pid": 42, "started": 7}]
    procs.save_run(records, path)
    assert procs.load_run(path) == records
    procs.save_run([], path)
    assert not path.exists()


def test_a_broken_run_file_reads_as_empty(tmp_path):
    path = tmp_path / "run.json"
    path.write_text("{not json")
    assert procs.load_run(path) == []


def test_output_goes_to_the_log(tmp_path):
    record = procs.spawn("echo", [sys.executable, "-c", "print('hello from child')"], log_dir=tmp_path)
    for _ in range(100):
        if "hello from child" in procs.tail(record["log"]):
            break
        time.sleep(0.05)
    assert "hello from child" in procs.tail(record["log"])
