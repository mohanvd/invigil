#include "addr_hash.h"

#include <string.h>

#include "sha256.h"

void addr_hash(const char *salt, const uint8_t addr[ADDR_LEN], char out[ADDR_HASH_LEN + 1]) {
    static const char hex[] = "0123456789abcdef";
    sha256_ctx ctx;
    uint8_t digest[SHA256_DIGEST_LEN];

    sha256_init(&ctx);
    sha256_update(&ctx, salt, strlen(salt));
    sha256_update(&ctx, addr, ADDR_LEN);
    sha256_final(&ctx, digest);

    for (int i = 0; i < ADDR_HASH_LEN / 2; i++) {
        out[2 * i] = hex[digest[i] >> 4];
        out[2 * i + 1] = hex[digest[i] & 0x0f];
    }
    out[ADDR_HASH_LEN] = '\0';
    memset(digest, 0, sizeof(digest));
}

bool addr_hash_is_valid(const char *s, size_t len) {
    if (len != ADDR_HASH_LEN) {
        return false;
    }
    for (size_t i = 0; i < len; i++) {
        char c = s[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) {
            return false;
        }
    }
    return true;
}
