import socket

from invigil import beacon

# The same vector as test_beacon_tag_vector in firmware/tests/test_portable.c.
SALT = "invigil-test-vector"
VECTOR = b"invigil broker 1883 52133b7ca99633f6"


def test_payload_matches_the_firmware_vector():
    assert beacon.payload(SALT, 1883, "192.168.43.17") == VECTOR


def test_tag_depends_on_the_salt_the_port_and_the_sender():
    base = beacon.tag(SALT, 1883, "192.168.43.17")
    assert len(base) == beacon.TAG_LEN
    assert beacon.tag(SALT + "x", 1883, "192.168.43.17") != base
    assert beacon.tag(SALT, 1884, "192.168.43.17") != base
    assert beacon.tag(SALT, 1883, "192.168.43.18") != base


def test_only_addresses_a_unit_could_reach_are_used():
    assert beacon.usable("192.168.43.17")
    assert beacon.usable("10.139.204.170")
    assert not beacon.usable("127.0.0.1")
    assert not beacon.usable("169.254.10.251")  # self-assigned: no DHCP on that adapter
    assert not beacon.usable("0.0.0.0")
    assert not beacon.usable("not an address")
    assert all(beacon.usable(ip) for ip in beacon.local_ipv4())


def test_send_once_sends_the_signed_payload_from_the_given_address():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rx:
        rx.bind(("127.0.0.1", 0))
        rx.settimeout(5)
        port = rx.getsockname()[1]
        sent = beacon.send_once(SALT, 1883, ["127.0.0.1"], udp_port=port, dest="127.0.0.1")
        data, sender = rx.recvfrom(100)
    assert sent == ["127.0.0.1"]
    assert sender[0] == "127.0.0.1"
    assert data == beacon.payload(SALT, 1883, "127.0.0.1")


def test_an_address_that_is_gone_is_skipped():
    # 192.0.2.1 is reserved for documentation, so no adapter has it.
    assert beacon.send_once(SALT, 1883, ["192.0.2.1"], dest="127.0.0.1") == []
