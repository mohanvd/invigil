import hashlib
import json

import pytest

from server import contract
from server.contract import ContractError, validate

TS = 1727340000123


def reading(**changes):
    r = {"ts": TS, "addr": "a91f03c2d4e8", "rssi": -58, "mfr": "0x004C"}
    r.update(changes)
    return r


def ble(**changes):
    """A ble message. Changes to ts and node go to the message, the rest to its reading."""
    msg = {"ts": TS + 877, "node": "N1", "readings": []}
    for key in ("ts", "node", "readings"):
        if key in changes:
            msg[key] = changes.pop(key)
    if not msg["readings"]:
        msg["readings"] = [reading(**changes)]
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
    "invigil/node/N2/ble",
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
    with pytest.raises(ContractError, match="NTP"):
        validate("ble", ble(readings=[reading(ts=1727340000)]))


def test_node_must_match_topic():
    with pytest.raises(ContractError, match="does not match"):
        validate("ble", ble(), "N9")


def test_second_node_is_rejected_until_phase_2():
    assert contract.NODE_IDS == ("N1",)
    with pytest.raises(ContractError, match="unknown node"):
        contract.topic("N2", "ble")
    with pytest.raises(ContractError, match="unknown node"):
        contract.parse_topic("invigil/node/N2/ble")
    with pytest.raises(ContractError, match="node must be one of"):
        validate("ble", ble(node="N2"))


@pytest.mark.parametrize("ts", [1727340000, 1727340000123000, -1, 1.7e12, True, "1727340000123"])
def test_bad_timestamps_rejected(ts):
    with pytest.raises(ContractError):
        validate("ble", ble(ts=ts))
    with pytest.raises(ContractError):
        validate("ble", ble(readings=[reading(ts=ts)]))


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
    del msg["readings"][0]["rssi"]
    with pytest.raises(ContractError, match="missing"):
        validate("ble", msg)
    with pytest.raises(ContractError, match="unexpected"):
        validate("ble", ble(payload="deadbeef"))
    msg = ble()
    del msg["readings"]
    with pytest.raises(ContractError, match="missing"):
        validate("ble", msg)
    msg = ble()
    msg["addr"] = "a91f03c2d4e8"  # the old one-reading shape at the top level
    with pytest.raises(ContractError, match="unexpected"):
        validate("ble", msg)


def test_old_single_reading_shape_rejected():
    old = {"ts": TS, "node": "N1", "addr": "a91f03c2d4e8", "rssi": -58, "mfr": "0x004C"}
    with pytest.raises(ContractError):
        validate("ble", old)


def test_several_readings_are_valid():
    msg = ble(readings=[reading(), reading(ts=TS + 300, addr="0f5e2b7a91c4", rssi=-81, mfr=None)])
    validate("ble", msg, "N1")


@pytest.mark.parametrize("readings", [[], None, "x", {"ts": TS}, [["a91f03c2d4e8", -58]], [None]])
def test_bad_readings_list_rejected(readings):
    with pytest.raises(ContractError):
        validate("ble", {"ts": TS, "node": "N1", "readings": readings})


def test_one_bad_reading_rejects_the_message():
    msg = ble(readings=[reading(), reading(rssi=3)])
    with pytest.raises(ContractError, match="reading rssi"):
        validate("ble", msg)


def test_ble_rows_flatten_one_row_per_reading():
    msg = ble(readings=[reading(), reading(ts=TS + 300, addr="0f5e2b7a91c4", rssi=-81, mfr=None)])
    rows = contract.ble_rows(validate("ble", msg))
    assert [tuple(r[k] for k in contract.BLE_ROW_FIELDS) for r in rows] == [
        (TS, "N1", "a91f03c2d4e8", -58, "0x004C"),
        (TS + 300, "N1", "0f5e2b7a91c4", -81, None),
    ]


def test_pack_ble_keeps_order_and_size_limit():
    readings = [reading(ts=TS + i, rssi=-(i % 128), mfr=None if i % 3 else "0x004C") for i in range(200)]
    messages = contract.pack_ble(TS + 1000, "N1", readings)
    assert len(messages) > 1
    assert [r for m in messages for r in m["readings"]] == readings
    for m in messages:
        validate("ble", m, "N1")
        assert len(contract.encode(m)) <= contract.MAX_BLE_PAYLOAD_BYTES
    # As few messages as possible: each one but the last could not take the next reading.
    for m, after in zip(messages, messages[1:]):
        bigger = {**m, "readings": [*m["readings"], after["readings"][0]]}
        assert len(contract.encode(bigger)) > contract.MAX_BLE_PAYLOAD_BYTES


def test_pack_ble_worst_case_reading_count():
    worst = reading(ts=contract.MAX_TS_MS, rssi=-127, mfr="0xFFFF")
    messages = contract.pack_ble(contract.MAX_TS_MS, "N1", [worst] * 40)
    assert len(contract.encode({"ts": 0, "addr": worst["addr"], "rssi": 0, "mfr": None})) < len(
        contract.encode(worst)) == 69
    assert len(messages[0]["readings"]) == 19  # docs/contract.md: at least 19


def test_pack_ble_empty_and_tiny_limit():
    assert contract.pack_ble(TS, "N1", []) == []
    # A limit too small for even one reading still sends each reading on its own.
    messages = contract.pack_ble(TS, "N1", [reading(), reading()], max_bytes=10)
    assert [len(m["readings"]) for m in messages] == [1, 1]


def test_encode_is_compact():
    assert b" " not in contract.encode(ble())
    assert json.loads(contract.encode(ble())) == ble()


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
VECTOR_ADDR_REVERSED = bytes([0xAB, 0x89, 0x67, 0x45, 0x23, 0x01])  # same address, LSB first
VECTOR_HASH = "41239c0be85e"
VECTOR_HASH_REVERSED = "5cebc32cde2c"  # what you get if the bytes are hashed LSB first


def test_shared_hash_vector():
    assert contract.hash_addr(VECTOR_ADDR, VECTOR_SALT) == VECTOR_HASH
    assert contract.hash_addr(VECTOR_ADDR_REVERSED[::-1], VECTOR_SALT) == VECTOR_HASH
    assert contract.hash_addr(VECTOR_ADDR_REVERSED, VECTOR_SALT) == VECTOR_HASH_REVERSED


def test_hash_addr_rejects_wrong_length():
    with pytest.raises(ValueError):
        contract.hash_addr(b"\x00" * 5, "salt")
