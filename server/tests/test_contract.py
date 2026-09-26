import hashlib

import pytest

from server import contract
from server.contract import ContractError, validate

TS = 1727340000123


def ble(**changes):
    msg = {"ts": TS, "node": "N1", "addr": "a91f03c2d4e8", "rssi": -58, "mfr": "0x004C"}
    msg.update(changes)
    return msg


def spectrum(**changes):
    msg = {"ts": TS, "node": "N1", "sweeps": 50, "hits": [0] * 126}
    msg.update(changes)
    return msg


def status(**changes):
    msg = {"ts": TS, "node": "N1", "uptime_s": 3600, "wifi_rssi": -61, "fw": "0.1.0"}
    msg.update(changes)
    return msg


def test_contract_examples_are_valid():
    validate("ble", ble(), "N1")
    validate("spectrum", spectrum(hits=[3] * 126), "N1")
    validate("status", status(), "N1")


def test_topics_round_trip():
    for node in contract.NODE_IDS:
        for kind in contract.KINDS:
            assert contract.parse_topic(contract.topic(node, kind)) == (node, kind)


@pytest.mark.parametrize("name", [
    "invigil/node/N4/ble",
    "invigil/node/N1/audio",
    "invigil/node/N1",
    "invigil/node/N1/ble/extra",
    "other/node/N1/ble",
])
def test_bad_topics_rejected(name):
    with pytest.raises(ContractError):
        contract.parse_topic(name)


def test_timestamp_in_seconds_gets_a_helpful_reason():
    with pytest.raises(ContractError, match="NTP"):
        validate("ble", ble(ts=1727340000))


def test_node_must_match_topic():
    with pytest.raises(ContractError, match="does not match"):
        validate("ble", ble(node="N2"), "N1")


@pytest.mark.parametrize("ts", [1727340000, 1727340000123000, -1, 1.7e12, True, "1727340000123"])
def test_bad_timestamps_rejected(ts):
    with pytest.raises(ContractError):
        validate("ble", ble(ts=ts))


@pytest.mark.parametrize("addr", [
    "A9:1F:03:C2:D4:E8",  # raw MAC, printed form
    "A91F03C2D4E8",  # uppercase
    "a91f03c2d4",  # too short
    "a91f03c2d4e8ff",  # too long
    "zz1f03c2d4e8",
    123456789012,
])
def test_bad_addresses_rejected(addr):
    with pytest.raises(ContractError):
        validate("ble", ble(addr=addr))


def test_error_message_never_echoes_the_value():
    raw_mac = "A9:1F:03:C2:D4:E8"
    with pytest.raises(ContractError) as err:
        validate("ble", ble(addr=raw_mac))
    assert raw_mac not in str(err.value)


@pytest.mark.parametrize("rssi", [-58.5, True, 5, -200, "-58"])
def test_bad_rssi_rejected(rssi):
    with pytest.raises(ContractError):
        validate("ble", ble(rssi=rssi))


def test_mfr_may_be_null():
    validate("ble", ble(mfr=None))


@pytest.mark.parametrize("mfr", ["0x004c", "004C", "0x4C", 76])
def test_bad_mfr_rejected(mfr):
    with pytest.raises(ContractError):
        validate("ble", ble(mfr=mfr))


def test_missing_and_extra_fields_rejected():
    msg = ble()
    del msg["rssi"]
    with pytest.raises(ContractError, match="missing"):
        validate("ble", msg)
    with pytest.raises(ContractError, match="unexpected"):
        validate("ble", ble(payload="deadbeef"))


@pytest.mark.parametrize("hits", [[0] * 125, [0] * 127, [51] + [0] * 125, [-1] + [0] * 125, "0" * 126])
def test_bad_hits_rejected(hits):
    with pytest.raises(ContractError):
        validate("spectrum", spectrum(hits=hits))


def test_bad_status_rejected():
    with pytest.raises(ContractError):
        validate("status", status(fw=""))
    with pytest.raises(ContractError):
        validate("status", status(uptime_s=-1))


def test_payload_must_be_an_object():
    with pytest.raises(ContractError):
        validate("ble", [ble()])


def test_hash_addr_matches_spec():
    salt = "test-salt"
    mac = bytes.fromhex("aabbccddeeff")
    expected = hashlib.sha256(b"test-salt" + mac).hexdigest()[:12]
    assert contract.hash_addr(mac, salt) == expected
    assert contract.hash_addr("AA:BB:CC:DD:EE:FF", salt) == expected
    assert contract.hash_addr("aa-bb-cc-dd-ee-ff", salt) == expected
    assert contract.hash_addr(mac, "other-salt") != expected
    validate("ble", ble(addr=expected))


# Shared test vector. The README lists the same values so the firmware can
# check its hashing and byte order. Change them in both places or neither.
VECTOR_SALT = "invigil-test-vector"
VECTOR_ADDR = "01:23:45:67:89:AB"
VECTOR_NIMBLE_VAL = bytes([0xAB, 0x89, 0x67, 0x45, 0x23, 0x01])  # ble_addr_t.val, LSB first
VECTOR_HASH = "41239c0be85e"
VECTOR_HASH_REVERSED = "5cebc32cde2c"  # what you get if val[] is hashed without reversing


def test_shared_hash_vector():
    assert contract.hash_addr(VECTOR_ADDR, VECTOR_SALT) == VECTOR_HASH
    assert contract.hash_addr(VECTOR_NIMBLE_VAL[::-1], VECTOR_SALT) == VECTOR_HASH
    assert contract.hash_addr(VECTOR_NIMBLE_VAL, VECTOR_SALT) == VECTOR_HASH_REVERSED


def test_hash_addr_rejects_wrong_length():
    with pytest.raises(ValueError):
        contract.hash_addr(b"\x00" * 5, "salt")
