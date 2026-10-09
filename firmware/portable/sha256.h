// SHA-256 (FIPS 180-4). Plain C with no Pico SDK includes, so the host tests
// can check it against the standard vectors.

#ifndef INVIGIL_SHA256_H
#define INVIGIL_SHA256_H

#include <stddef.h>
#include <stdint.h>

#define SHA256_DIGEST_LEN 32

typedef struct {
    uint32_t state[8];
    uint64_t total_len;  // bytes hashed so far
    uint8_t block[64];
    size_t block_len;    // bytes waiting in block
} sha256_ctx;

void sha256_init(sha256_ctx *ctx);
void sha256_update(sha256_ctx *ctx, const void *data, size_t len);
void sha256_final(sha256_ctx *ctx, uint8_t digest[SHA256_DIGEST_LEN]);

#endif
