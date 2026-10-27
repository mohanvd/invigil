"""Check the firmware's sample messages against the MQTT contract.

The host test program (firmware/tests/test_portable.c) writes a sample of
every message kind the unit builds, plus address hash vectors. This script
runs the messages through server/contract.py, the same checks the logger
uses, and compares the firmware's hashes with contract.hash_addr(). So the
firmware payloads and the contract cannot drift apart.

Run from the repo root after the host tests:
    python firmware/tests/check_contract.py firmware/build/tests/samples.tsv
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server import contract  # noqa: E402


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise contract.ContractError("duplicate key in payload")
    return dict(pairs)


def check(path: Path) -> list[str]:
    errors = []
    kinds: Counter[str] = Counter()
    hashes = 0
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        fields = line.split("\t")
        try:
            if fields[0] == "msg" and len(fields) == 3:
                _, topic, raw = fields
                node, kind = contract.parse_topic(topic)
                payload = json.loads(raw, object_pairs_hook=no_duplicate_keys)
                contract.validate(kind, payload, node)
                if kind == "ble" and len(raw.encode("utf-8")) > contract.MAX_BLE_PAYLOAD_BYTES:
                    raise ValueError(f"ble payload is over {contract.MAX_BLE_PAYLOAD_BYTES} bytes")
                kinds[kind] += 1
            elif fields[0] == "hash" and len(fields) == 4:
                _, salt_hex, addr_hex, firmware_hash = fields
                salt = bytes.fromhex(salt_hex).decode("utf-8")
                expected = contract.hash_addr(bytes.fromhex(addr_hex), salt)
                if firmware_hash != expected:
                    raise ValueError(f"firmware hash {firmware_hash} != contract hash {expected}")
                hashes += 1
            else:
                raise ValueError("unknown line format")
        except (contract.ContractError, ValueError) as e:
            errors.append(f"{path}:{lineno}: {e}")

    for kind in contract.KINDS:
        if kinds[kind] == 0:
            errors.append(f"no {kind} sample in {path}")
    if hashes == 0:
        errors.append(f"no hash vectors in {path}")
    if not errors:
        counts = ", ".join(f"{kinds[k]} {k}" for k in contract.KINDS)
        print(f"contract check passed: {counts}, {hashes} hash vectors")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    errors = check(Path(argv[1]))
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
