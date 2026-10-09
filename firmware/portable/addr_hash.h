// Address hashing rule from docs/hashing.md:
//   sha256(salt as UTF-8 bytes + the 6 address bytes), first 12 hex chars.
// server/contract.py hash_addr() is the reference implementation.

#ifndef INVIGIL_ADDR_HASH_H
#define INVIGIL_ADDR_HASH_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ADDR_LEN 6
#define ADDR_HASH_LEN 12

// Hashes the 6 bytes in the order given. The caller is responsible for that
// order being the printed one, most significant byte first.
// out receives 12 lowercase hex chars and a terminating NUL.
void addr_hash(const char *salt, const uint8_t addr[ADDR_LEN], char out[ADDR_HASH_LEN + 1]);

// True if s starts with exactly ADDR_HASH_LEN lowercase hex chars, the only
// form an address may take outside the hashing function.
bool addr_hash_is_valid(const char *s, size_t len);

#endif
