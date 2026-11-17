#include "beacon.h"

#include <stdio.h>
#include <string.h>

#include "sha256.h"

#define BEACON_PREFIX "invigil broker "
#define BEACON_PREFIX_LEN (sizeof(BEACON_PREFIX) - 1)
#define SHA256_BLOCK_LEN 64

void hmac_sha256(const void *key, size_t key_len, const void *msg, size_t msg_len, uint8_t out[32]) {
    uint8_t block[SHA256_BLOCK_LEN] = {0};
    uint8_t pad[SHA256_BLOCK_LEN];
    uint8_t inner[SHA256_DIGEST_LEN];
    sha256_ctx ctx;

    // A key longer than one block is replaced by its hash (RFC 2104).
    if (key_len > SHA256_BLOCK_LEN) {
        sha256_init(&ctx);
        sha256_update(&ctx, key, key_len);
        sha256_final(&ctx, block);
    } else if (key_len > 0) {
        memcpy(block, key, key_len);
    }

    for (size_t i = 0; i < SHA256_BLOCK_LEN; i++) {
        pad[i] = block[i] ^ 0x36;
    }
    sha256_init(&ctx);
    sha256_update(&ctx, pad, sizeof(pad));
    sha256_update(&ctx, msg, msg_len);
    sha256_final(&ctx, inner);

    for (size_t i = 0; i < SHA256_BLOCK_LEN; i++) {
        pad[i] = block[i] ^ 0x5c;
    }
    sha256_init(&ctx);
    sha256_update(&ctx, pad, sizeof(pad));
    sha256_update(&ctx, inner, sizeof(inner));
    sha256_final(&ctx, out);
}

void beacon_tag(const char *key, uint16_t port, const uint8_t ip[4], char out[BEACON_TAG_LEN + 1]) {
    static const char hex[] = "0123456789abcdef";
    char msg[BEACON_PREFIX_LEN + sizeof("65535 255.255.255.255")];
    uint8_t mac[SHA256_DIGEST_LEN];
    int n = snprintf(msg, sizeof(msg), BEACON_PREFIX "%u %u.%u.%u.%u", (unsigned)port, (unsigned)ip[0],
                     (unsigned)ip[1], (unsigned)ip[2], (unsigned)ip[3]);
    hmac_sha256(key, strlen(key), msg, (size_t)n, mac);
    for (int i = 0; i < BEACON_TAG_LEN / 2; i++) {
        out[2 * i] = hex[mac[i] >> 4];
        out[2 * i + 1] = hex[mac[i] & 0xf];
    }
    out[BEACON_TAG_LEN] = '\0';
}

bool beacon_verify(const char *key, const uint8_t *data, size_t len, const uint8_t ip[4], uint16_t *port) {
    if (key[0] == '\0' || len > BEACON_MAX_LEN) {
        return false;
    }
    // One line end is allowed, so the beacon can be sent by hand for a test.
    if (len > 0 && data[len - 1] == '\n') {
        len--;
    }
    if (len > 0 && data[len - 1] == '\r') {
        len--;
    }
    if (len < BEACON_PREFIX_LEN || memcmp(data, BEACON_PREFIX, BEACON_PREFIX_LEN) != 0) {
        return false;
    }

    // The port: 1 to 5 digits, no leading zero, 1 to 65535.
    size_t i = BEACON_PREFIX_LEN;
    uint32_t value = 0;
    size_t digits = 0;
    while (i < len && data[i] >= '0' && data[i] <= '9' && digits < 6) {
        value = value * 10 + (uint32_t)(data[i] - '0');
        i++;
        digits++;
    }
    if (digits == 0 || digits > 5 || data[BEACON_PREFIX_LEN] == '0' || value > 65535) {
        return false;
    }
    if (len != i + 1 + BEACON_TAG_LEN || data[i] != ' ') {
        return false;
    }

    // Compare every char, so the time taken does not show where a wrong tag
    // first differs.
    char want[BEACON_TAG_LEN + 1];
    beacon_tag(key, (uint16_t)value, ip, want);
    uint8_t diff = 0;
    for (size_t k = 0; k < BEACON_TAG_LEN; k++) {
        diff |= (uint8_t)(data[i + 1 + k] ^ (uint8_t)want[k]);
    }
    if (diff != 0) {
        return false;
    }
    *port = (uint16_t)value;
    return true;
}

bool beacon_addr_equal(const beacon_addr_t *a, const beacon_addr_t *b) {
    return memcmp(a->ip, b->ip, sizeof(a->ip)) == 0 && a->port == b->port;
}

void beacon_pick_init(beacon_pick_t *p) {
    memset(p, 0, sizeof(*p));
}

static bool pick_is_live(const beacon_pick_t *p, uint32_t now_ms) {
    // Unsigned subtraction stays right when the millisecond counter wraps.
    return p->have && (uint32_t)(now_ms - p->seen_ms) < BEACON_LOST_MS;
}

void beacon_pick_heard(beacon_pick_t *p, const beacon_addr_t *from, uint32_t now_ms) {
    if (pick_is_live(p, now_ms) && !beacon_addr_equal(&p->addr, from)) {
        return;  // the sender already followed is still there
    }
    p->have = true;
    p->addr = *from;
    p->seen_ms = now_ms;
}

bool beacon_pick_live(const beacon_pick_t *p, uint32_t now_ms, beacon_addr_t *out) {
    if (!pick_is_live(p, now_ms)) {
        return false;
    }
    *out = p->addr;
    return true;
}

bool beacon_pick_last(const beacon_pick_t *p, beacon_addr_t *out) {
    if (!p->have) {
        return false;
    }
    *out = p->addr;
    return true;
}
