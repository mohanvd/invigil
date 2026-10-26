import socket
import threading
import time

import pytest

from invigil import ntp


def test_offset_and_delay_follow_the_sntp_formula():
    # Server clock 1.5 s ahead, 40 ms each way, 10 ms inside the server.
    t1 = 1000.0
    t2 = t1 + 0.040 + 1.5
    t3 = t2 + 0.010
    t4 = t1 + 0.040 + 0.010 + 0.040
    offset, delay = ntp.offset_and_delay(t1, t2, t3, t4)
    assert offset == pytest.approx(1.5)
    assert delay == pytest.approx(0.080)


def test_ntp_timestamps_round_trip():
    t = 1_793_019_264.25
    assert ntp.from_ntp(ntp.to_ntp(t)) == pytest.approx(t, abs=1e-6)


def fake_server(skew_s: float, mode: int = 4):
    """A local UDP server that answers like an NTP server whose clock is skew_s ahead."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))

    def serve():
        data, addr = sock.recvfrom(512)
        received = time.time() + skew_s
        reply = bytearray(48)
        reply[0] = 0x20 | mode
        reply[1] = 2  # stratum
        reply[24:32] = data[40:48]  # originate = the client's transmit time
        reply[32:40] = ntp.to_ntp(received)
        reply[40:48] = ntp.to_ntp(time.time() + skew_s)
        sock.sendto(bytes(reply), addr)
        sock.close()

    threading.Thread(target=serve, daemon=True).start()
    return sock.getsockname()[1]


def test_query_measures_the_offset_of_a_server():
    port = fake_server(skew_s=1.45)
    offset, delay = ntp.query("127.0.0.1", port, timeout=2)
    assert offset == pytest.approx(1.45, abs=0.05)
    assert 0 <= delay < 0.5


def test_check_clock_warns_over_100_ms():
    check = ntp.check_clock("127.0.0.1", fake_server(skew_s=1.45))
    assert not check.ok
    text = check.describe()
    assert "behind 127.0.0.1" in text and "WARNING" in text and "Sync now" in text


def test_check_clock_is_quiet_when_close():
    check = ntp.check_clock("127.0.0.1", fake_server(skew_s=0.0))
    assert check.ok
    assert "WARNING" not in check.describe()


def test_a_reply_that_is_not_from_a_server_is_refused():
    check = ntp.check_clock("127.0.0.1", fake_server(skew_s=0.0, mode=3))
    assert check.offset_ms is None
    assert "could not reach" in check.describe()


def test_no_answer_gives_an_unknown_offset():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))  # bound, never answers
    try:
        check = ntp.check_clock("127.0.0.1", sock.getsockname()[1], timeout=0.2)
    finally:
        sock.close()
    assert check.offset_ms is None and not check.ok
