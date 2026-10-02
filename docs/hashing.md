# Address hashing

Invigil never stores a raw Bluetooth address. The unit hashes every BLE address before sending it, and the server refuses anything that is not a hash.

## The rule

`sha256(salt + 6 address bytes)`, keeping the first 12 hex characters.

- The salt is its UTF-8 bytes. It is a secret: it lives in the gitignored `server/config.toml` and in the firmware secrets file, and both must hold the same value.
- The address bytes go most significant first, in the order the address is printed.
- `hash_addr` in `server/contract.py` is the reference implementation.

## Test vector

The byte order BTstack hands addresses over in is not assumed. The firmware must reproduce this test vector at boot, and that is checked on real hardware:

| Input | Value |
| --- | --- |
| Salt | `invigil-test-vector` |
| Address as printed | `01:23:45:67:89:AB` |
| Bytes hashed | `invigil-test-vector` followed by `01 23 45 67 89 AB` |
| **Expected hash** | **`41239c0be85e`** |
| Hash with the wrong byte order | `5cebc32cde2c` |

If the unit prints `5cebc32cde2c`, the address bytes are reversed and the firmware must flip them before hashing.

The server test `test_shared_hash_vector` checks the same values. If you change them, change both.

The salt and address above are made up for this test. Never use `invigil-test-vector` as a real salt.

## Limits

- A 12-character hash is a pseudonym, not anonymity. Anyone who knows the salt can hash a known address and look for it in the data. Keep the salt secret and keep raw captures on the laptop.
- Phones and many earbuds rotate their BLE address every few minutes, so one device can appear under several hashes. See the open decisions in the [data collection protocol](data-protocol.md).
