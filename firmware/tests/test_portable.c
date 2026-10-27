// Host tests for the firmware code that does not need the Pico SDK.
//
// Usage: test_portable [samples.tsv]
// With a path, it also writes sample topics and payloads for every message
// kind, plus address hash vectors. CI checks that file with
// firmware/tests/check_contract.py, which uses server/contract.py.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "addr_hash.h"
#include "adv_data.h"
#include "ble_ring.h"
#include "nrf24.h"
#include "payload.h"
#include "sha256.h"
#include "spectrum.h"

static int checks;
static int failures;

#define CHECK(cond)                                                       \
    do {                                                                  \
        checks++;                                                         \
        if (!(cond)) {                                                    \
            failures++;                                                   \
            fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond); \
        }                                                                 \
    } while (0)

#define CHECK_STR(got, want)                                              \
    do {                                                                  \
        checks++;                                                         \
        if (strcmp((got), (want)) != 0) {                                 \
            failures++;                                                   \
            fprintf(stderr, "%s:%d: got  \"%s\"\n%*swant \"%s\"\n", __FILE__, __LINE__, (got), \
                    (int)strlen(__FILE__) + 8, "", (want));               \
        }                                                                 \
    } while (0)

static const uint64_t TS = 1727340000123ULL;  // the example ts in docs/contract.md
static const uint8_t VECTOR_ADDR[ADDR_LEN] = {0x01, 0x23, 0x45, 0x67, 0x89, 0xAB};  // docs/hashing.md

static void to_hex(const uint8_t *data, size_t len, char *out) {
    static const char hex[] = "0123456789abcdef";
    for (size_t i = 0; i < len; i++) {
        out[2 * i] = hex[data[i] >> 4];
        out[2 * i + 1] = hex[data[i] & 0xf];
    }
    out[2 * len] = '\0';
}

static void sha256_hex(const void *data, size_t len, char out[65]) {
    sha256_ctx ctx;
    uint8_t digest[SHA256_DIGEST_LEN];
    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, digest);
    to_hex(digest, sizeof(digest), out);
}

// ---------------------------------------------------------------- SHA-256

static void test_sha256_standard_vectors(void) {
    char hex[65];

    sha256_hex("", 0, hex);
    CHECK_STR(hex, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");

    sha256_hex("abc", 3, hex);
    CHECK_STR(hex, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");

    const char *two_blocks = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    sha256_hex(two_blocks, strlen(two_blocks), hex);
    CHECK_STR(hex, "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");

    // One million 'a', fed in uneven chunks to exercise the block buffering.
    static char chunk[997];
    memset(chunk, 'a', sizeof(chunk));
    sha256_ctx ctx;
    uint8_t digest[SHA256_DIGEST_LEN];
    sha256_init(&ctx);
    size_t left = 1000000;
    while (left > 0) {
        size_t n = left < sizeof(chunk) ? left : sizeof(chunk);
        sha256_update(&ctx, chunk, n);
        left -= n;
    }
    sha256_final(&ctx, digest);
    to_hex(digest, sizeof(digest), hex);
    CHECK_STR(hex, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
}

// ---------------------------------------------------------- address hash

static void test_addr_hash_vector_both_orders(void) {
    char out[ADDR_HASH_LEN + 1];
    uint8_t reversed[ADDR_LEN];
    for (int i = 0; i < ADDR_LEN; i++) {
        reversed[i] = VECTOR_ADDR[ADDR_LEN - 1 - i];
    }

    addr_hash("invigil-test-vector", VECTOR_ADDR, out);
    CHECK_STR(out, "41239c0be85e");  // printed order, the correct one

    addr_hash("invigil-test-vector", reversed, out);
    CHECK_STR(out, "5cebc32cde2c");  // what reversed bytes give
}

static void test_addr_hash_validity(void) {
    CHECK(addr_hash_is_valid("41239c0be85e", 12));
    CHECK(!addr_hash_is_valid("41239C0BE85E", 12));       // uppercase
    CHECK(!addr_hash_is_valid("41239c0be85", 11));        // short
    CHECK(!addr_hash_is_valid("41239c0be85e0", 13));      // long
    CHECK(!addr_hash_is_valid("A9:1F:03:C2:D4:E8", 17));  // raw address
    CHECK(!addr_hash_is_valid("zz239c0be85e", 12));
}

// ------------------------------------------------------ manufacturer ID

static void test_company_id_found(void) {
    // Flags, then Manufacturer Specific Data with company ID 0x004C.
    const uint8_t adv[] = {0x02, 0x01, 0x06, 0x05, 0xFF, 0x4C, 0x00, 0x10, 0x05};
    uint16_t id = 0;
    CHECK(adv_find_company_id(adv, sizeof(adv), &id));
    CHECK(id == 0x004C);

    // Manufacturer data that is only the company ID, at the very end.
    const uint8_t end[] = {0x02, 0x01, 0x06, 0x03, 0xFF, 0xE0, 0x00};
    CHECK(adv_find_company_id(end, sizeof(end), &id));
    CHECK(id == 0x00E0);

    // The first complete one wins.
    const uint8_t two[] = {0x03, 0xFF, 0x75, 0x00, 0x03, 0xFF, 0x4C, 0x00};
    CHECK(adv_find_company_id(two, sizeof(two), &id));
    CHECK(id == 0x0075);
}

static void test_company_id_absent(void) {
    uint16_t id = 0xBEEF;
    const uint8_t flags_and_uuid[] = {0x02, 0x01, 0x06, 0x03, 0x03, 0x0F, 0x18};
    CHECK(!adv_find_company_id(flags_and_uuid, sizeof(flags_and_uuid), &id));
    CHECK(!adv_find_company_id(flags_and_uuid, 0, &id));
    CHECK(id == 0xBEEF);  // untouched when not found
}

static void test_company_id_malformed(void) {
    uint16_t id = 0;
    // Manufacturer field too short for a company ID, followed by a good one.
    const uint8_t short_then_good[] = {0x02, 0xFF, 0x4C, 0x03, 0xFF, 0x75, 0x00};
    CHECK(adv_find_company_id(short_then_good, sizeof(short_then_good), &id));
    CHECK(id == 0x0075);

    // Only the short one.
    const uint8_t only_short[] = {0x02, 0xFF, 0x4C};
    CHECK(!adv_find_company_id(only_short, sizeof(only_short), &id));

    // Length byte runs past the end of the data.
    const uint8_t overrun[] = {0x02, 0x01, 0x06, 0x09, 0xFF, 0x4C, 0x00};
    CHECK(!adv_find_company_id(overrun, sizeof(overrun), &id));

    // Overrun on the last byte only.
    const uint8_t overrun_by_one[] = {0x04, 0xFF, 0x4C, 0x00};
    CHECK(!adv_find_company_id(overrun_by_one, sizeof(overrun_by_one), &id));

    // A zero length byte ends the data, so the field after it is ignored.
    const uint8_t terminated[] = {0x02, 0x01, 0x06, 0x00, 0x03, 0xFF, 0x4C, 0x00};
    CHECK(!adv_find_company_id(terminated, sizeof(terminated), &id));

    // A lone length byte.
    const uint8_t lone[] = {0x05};
    CHECK(!adv_find_company_id(lone, sizeof(lone), &id));
}

static void test_company_id_format(void) {
    char out[7];
    adv_format_company_id(0x004C, out);
    CHECK_STR(out, "0x004C");
    adv_format_company_id(0xABCD, out);
    CHECK_STR(out, "0xABCD");
    adv_format_company_id(0x0000, out);
    CHECK_STR(out, "0x0000");
}

// --------------------------------------------------------------- spectrum

static void test_spectrum_counting(void) {
    spectrum_t s;
    uint8_t rpd[SPECTRUM_CHANNELS];
    spectrum_reset(&s);
    CHECK(s.sweeps == 0);

    for (int sweep = 0; sweep < 10; sweep++) {
        memset(rpd, 0, sizeof(rpd));
        rpd[0] = 1;                  // every sweep
        if (sweep % 2 == 0) {
            rpd[42] = 1;             // every other sweep
        }
        if (sweep == 3) {
            rpd[125] = 7;            // any nonzero value counts once
        }
        CHECK(spectrum_add_sweep(&s, rpd));
    }
    CHECK(s.sweeps == 10);
    CHECK(s.hits[0] == 10);
    CHECK(s.hits[42] == 5);
    CHECK(s.hits[125] == 1);
    CHECK(s.hits[1] == 0);

    spectrum_reset(&s);
    CHECK(s.sweeps == 0 && s.hits[0] == 0);
}

static void test_spectrum_caps_at_contract_max(void) {
    spectrum_t s;
    uint8_t rpd[SPECTRUM_CHANNELS];
    memset(rpd, 1, sizeof(rpd));
    spectrum_reset(&s);
    s.sweeps = SPECTRUM_MAX_SWEEPS - 1;
    for (int c = 0; c < SPECTRUM_CHANNELS; c++) {
        s.hits[c] = SPECTRUM_MAX_SWEEPS - 1;
    }
    CHECK(spectrum_add_sweep(&s, rpd));
    CHECK(s.sweeps == SPECTRUM_MAX_SWEEPS);
    CHECK(s.hits[0] == SPECTRUM_MAX_SWEEPS);
    CHECK(!spectrum_add_sweep(&s, rpd));
    CHECK(s.sweeps == SPECTRUM_MAX_SWEEPS);
    CHECK(s.hits[0] == SPECTRUM_MAX_SWEEPS);
}

// ---------------------------------------------------------------- ring

static ble_reading_t reading(uint64_t ts) {
    ble_reading_t r;
    memset(&r, 0, sizeof(r));
    r.ts_ms = ts;
    strcpy(r.addr, "41239c0be85e");
    r.rssi = -60;
    return r;
}

static void test_ring_fifo_and_drop_oldest(void) {
    ble_reading_t storage[4];
    ble_ring_t ring;
    ble_reading_t out;
    ble_ring_init(&ring, storage, 4);

    CHECK(!ble_ring_peek(&ring, &out));
    ble_ring_pop(&ring);  // popping empty is harmless
    CHECK(ring.count == 0);

    for (uint64_t i = 1; i <= 3; i++) {
        ble_reading_t r = reading(i);
        ble_ring_push(&ring, &r);
    }
    CHECK(ring.count == 3 && ring.dropped == 0);
    CHECK(ble_ring_peek(&ring, &out) && out.ts_ms == 1);
    ble_ring_pop(&ring);
    CHECK(ble_ring_peek(&ring, &out) && out.ts_ms == 2);

    // Fill past capacity: 2, 3, 4, 5, then 6 and 7 push out 2 and 3.
    for (uint64_t i = 4; i <= 7; i++) {
        ble_reading_t r = reading(i);
        ble_ring_push(&ring, &r);
    }
    CHECK(ring.count == 4);
    CHECK(ring.dropped == 2);
    // peek_at walks from the oldest across the wrap, and stops at the end.
    for (uint32_t i = 0; i < 4; i++) {
        CHECK(ble_ring_peek_at(&ring, i, &out) && out.ts_ms == 4 + i);
    }
    CHECK(!ble_ring_peek_at(&ring, 4, &out));
    for (uint64_t want = 4; want <= 7; want++) {
        CHECK(ble_ring_peek(&ring, &out) && out.ts_ms == want);
        ble_ring_pop(&ring);
    }
    CHECK(ring.count == 0);
    CHECK(!ble_ring_peek(&ring, &out));
}

// ------------------------------------------------------------- payloads

static void test_topics(void) {
    char t[TOPIC_MAX_LEN];
    CHECK(payload_topic(t, sizeof(t), "N1", "ble") > 0);
    CHECK_STR(t, "invigil/node/N1/ble");
    CHECK(payload_topic(t, sizeof(t), "N1", "spectrum") > 0);
    CHECK_STR(t, "invigil/node/N1/spectrum");
    CHECK(payload_topic(t, sizeof(t), "N1", "status") > 0);
    CHECK_STR(t, "invigil/node/N1/status");
    CHECK(payload_topic(t, sizeof(t), "N1", "detection") == 0);  // proposed only, not built here
    CHECK(payload_topic(t, sizeof(t), "N1", "audio") == 0);
    CHECK(payload_topic(t, sizeof(t), "N/1", "ble") == 0);
    CHECK(payload_topic(t, sizeof(t), "N+", "ble") == 0);
    CHECK(payload_topic(t, sizeof(t), "", "ble") == 0);
    CHECK(payload_topic(t, 10, "N1", "ble") == 0);  // too small
}

static ble_reading_t ble_reading(uint64_t ts, const char *addr, int rssi, bool has_mfr, uint16_t mfr) {
    ble_reading_t r;
    memset(&r, 0, sizeof(r));
    r.ts_ms = ts;
    strncpy(r.addr, addr, sizeof(r.addr) - 1);
    r.rssi = (int8_t)rssi;
    r.has_mfr = has_mfr;
    r.mfr = mfr;
    return r;
}

static void test_ble_batch(void) {
    char p[PAYLOAD_BLE_MAX_LEN];
    ble_batch_t b;
    CHECK(ble_batch_begin(&b, p, sizeof(p), TS + 877, "N1"));
    ble_reading_t r1 = ble_reading(TS, "a91f03c2d4e8", -58, true, 0x004C);
    ble_reading_t r2 = ble_reading(TS + 287, "0f5e2b7a91c4", -127, false, 0);
    ble_reading_t r3 = ble_reading(TS + 300, "a91f03c2d4e8", 0, true, 0xFFFF);
    CHECK(ble_batch_add(&b, &r1) == BLE_BATCH_ADDED);
    CHECK(ble_batch_add(&b, &r2) == BLE_BATCH_ADDED);
    CHECK(ble_batch_add(&b, &r3) == BLE_BATCH_ADDED);
    CHECK(b.count == 3);
    size_t n = ble_batch_finish(&b);
    CHECK_STR(p, "{\"ts\":1727340001000,\"node\":\"N1\",\"readings\":["
                 "{\"ts\":1727340000123,\"addr\":\"a91f03c2d4e8\",\"rssi\":-58,\"mfr\":\"0x004C\"},"
                 "{\"ts\":1727340000410,\"addr\":\"0f5e2b7a91c4\",\"rssi\":-127,\"mfr\":null},"
                 "{\"ts\":1727340000423,\"addr\":\"a91f03c2d4e8\",\"rssi\":0,\"mfr\":\"0xFFFF\"}]}");
    CHECK(n == strlen(p));

    // One reading.
    CHECK(ble_batch_begin(&b, p, sizeof(p), TS + 877, "N1"));
    CHECK(ble_batch_add(&b, &r1) == BLE_BATCH_ADDED);
    ble_batch_finish(&b);
    CHECK_STR(p, "{\"ts\":1727340001000,\"node\":\"N1\",\"readings\":["
                 "{\"ts\":1727340000123,\"addr\":\"a91f03c2d4e8\",\"rssi\":-58,\"mfr\":\"0x004C\"}]}");

    // No readings: nothing to send.
    CHECK(ble_batch_begin(&b, p, sizeof(p), TS, "N1"));
    CHECK(ble_batch_finish(&b) == 0);
    CHECK(p[0] == '\0');
}

static void test_ble_batch_rejects_off_contract(void) {
    char p[PAYLOAD_BLE_MAX_LEN];
    ble_batch_t b;
    const ble_reading_t good = ble_reading(TS, "a91f03c2d4e8", -58, false, 0);
    const ble_reading_t bad[] = {
        // Never a raw address, in any form.
        ble_reading(TS, "A9:1F:03:C2:D4:E8", -58, false, 0),
        // A reading holds at most 12 address chars, so a too-long one cannot
        // reach the builder. Too short, uppercase and non-hex can.
        ble_reading(TS, "a91f03c2d4e", -58, false, 0),
        ble_reading(TS, "A91F03C2D4E8", -58, false, 0),
        ble_reading(TS, "a91f03c2d4eg", -58, false, 0),
        // RSSI outside -127..0.
        ble_reading(TS, "a91f03c2d4e8", 1, false, 0),
        ble_reading(TS, "a91f03c2d4e8", -128, false, 0),
        // Clock not synced, or seconds instead of ms, or microseconds.
        ble_reading(0, "a91f03c2d4e8", -58, false, 0),
        ble_reading(1727340000ULL, "a91f03c2d4e8", -58, false, 0),
        ble_reading(1727340000123000ULL, "a91f03c2d4e8", -58, false, 0),
    };
    CHECK(ble_batch_begin(&b, p, sizeof(p), TS, "N1"));
    CHECK(ble_batch_add(&b, &good) == BLE_BATCH_ADDED);
    size_t before = b.len;
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
        CHECK(ble_batch_add(&b, &bad[i]) == BLE_BATCH_INVALID);
    }
    CHECK(b.count == 1 && b.len == before);  // unchanged by the bad ones
    ble_batch_finish(&b);
    CHECK(strstr(p, "A9:1F") == NULL);

    // The message itself: clock, node, buffer.
    CHECK(!ble_batch_begin(&b, p, sizeof(p), 1727340000ULL, "N1"));
    CHECK(p[0] == '\0');
    CHECK(!ble_batch_begin(&b, p, sizeof(p), TS, ""));
    CHECK(!ble_batch_begin(&b, p, sizeof(p), TS, "N1\""));
    CHECK(!ble_batch_begin(&b, p, 20, TS, "N1"));
    CHECK(!ble_batch_begin(&b, p, 0, TS, "N1"));
}

static void test_ble_batch_size_limit(void) {
    // The worst case reading, 69 bytes: 19 fit in 1400 bytes, as docs/contract.md says.
    char p[PAYLOAD_BLE_MAX_LEN];
    ble_batch_t b;
    const ble_reading_t worst = ble_reading(CONTRACT_MAX_TS_MS, "a91f03c2d4e8", -127, true, 0xFFFF);
    CHECK(ble_batch_begin(&b, p, sizeof(p), CONTRACT_MAX_TS_MS, "N1"));
    int added = 0;
    while (ble_batch_add(&b, &worst) == BLE_BATCH_ADDED) {
        added++;
    }
    CHECK(added == 19);
    CHECK(ble_batch_add(&b, &worst) == BLE_BATCH_FULL);  // still full, still unchanged
    size_t n = ble_batch_finish(&b);
    CHECK(n > 0 && n <= CONTRACT_MAX_BLE_PAYLOAD);
    CHECK(n == strlen(p));
    CHECK(p[n - 2] == ']' && p[n - 1] == '}');

    // A bigger buffer does not raise the limit.
    static char big[4 * PAYLOAD_BLE_MAX_LEN];
    CHECK(ble_batch_begin(&b, big, sizeof(big), CONTRACT_MAX_TS_MS, "N1"));
    added = 0;
    while (ble_batch_add(&b, &worst) == BLE_BATCH_ADDED) {
        added++;
    }
    CHECK(added == 19);
    CHECK(ble_batch_finish(&b) <= CONTRACT_MAX_BLE_PAYLOAD);

    // A smaller buffer lowers it, and the result always fits with its NUL.
    for (size_t cap = 20; cap < 400; cap++) {
        char small[400];
        memset(small, 'x', sizeof(small));
        if (!ble_batch_begin(&b, small, cap, CONTRACT_MAX_TS_MS, "N1")) {
            continue;
        }
        ble_batch_result_t first = ble_batch_add(&b, &worst);
        while (ble_batch_add(&b, &worst) == BLE_BATCH_ADDED) {
        }
        size_t len = ble_batch_finish(&b);
        CHECK(len < cap);
        CHECK(small[cap] == 'x');  // nothing written past the buffer
        if (first == BLE_BATCH_INVALID) {
            CHECK(len == 0);  // not even one reading fits: never FULL, so the caller moves on
        } else {
            CHECK(len == strlen(small));
        }
    }
}

static void test_spectrum_payload(void) {
    spectrum_t s;
    spectrum_reset(&s);
    s.sweeps = 50;
    s.hits[0] = 3;
    s.hits[125] = 50;

    char want[PAYLOAD_SPECTRUM_MAX_LEN];
    int pos = snprintf(want, sizeof(want), "{\"ts\":1727340000123,\"node\":\"N1\",\"sweeps\":50,\"hits\":[3");
    for (int c = 1; c < 125; c++) {
        pos += snprintf(want + pos, sizeof(want) - (size_t)pos, ",0");
    }
    snprintf(want + pos, sizeof(want) - (size_t)pos, ",50]}");

    char p[PAYLOAD_SPECTRUM_MAX_LEN];
    CHECK(payload_spectrum(p, sizeof(p), TS, "N1", &s) == strlen(want));
    CHECK_STR(p, want);
}

static void test_spectrum_payload_limits(void) {
    spectrum_t s;
    char p[PAYLOAD_SPECTRUM_MAX_LEN];

    // The largest possible message fits the buffer.
    spectrum_reset(&s);
    s.sweeps = SPECTRUM_MAX_SWEEPS;
    for (int c = 0; c < SPECTRUM_CHANNELS; c++) {
        s.hits[c] = SPECTRUM_MAX_SWEEPS;
    }
    CHECK(payload_spectrum(p, sizeof(p), CONTRACT_MAX_TS_MS, "N1", &s) > 0);

    spectrum_reset(&s);
    CHECK(payload_spectrum(p, sizeof(p), TS, "N1", &s) == 0);  // no sweeps: nothing to send

    s.sweeps = 5;
    s.hits[10] = 6;  // more hits than sweeps
    CHECK(payload_spectrum(p, sizeof(p), TS, "N1", &s) == 0);

    s.hits[10] = 5;
    CHECK(payload_spectrum(p, 200, TS, "N1", &s) == 0);  // buffer too small
}

static void test_status_payload(void) {
    char p[PAYLOAD_STATUS_MAX_LEN];
    payload_status(p, sizeof(p), TS, "N1", 3600, -61, "0.1.0");
    CHECK_STR(p, "{\"ts\":1727340000123,\"node\":\"N1\",\"uptime_s\":3600,\"wifi_rssi\":-61,\"fw\":\"0.1.0\"}");

    payload_status(p, sizeof(p), TS, "N1", 0, 0, "a\"b\\c");
    CHECK_STR(p, "{\"ts\":1727340000123,\"node\":\"N1\",\"uptime_s\":0,\"wifi_rssi\":0,\"fw\":\"a\\\"b\\\\c\"}");

    CHECK(payload_status(p, sizeof(p), TS, "N1", 3600, -61, "") == 0);
    CHECK(payload_status(p, sizeof(p), TS, "N1", 3600, -61, "0123456789012345678901234567890123") == 0);
    CHECK(payload_status(p, sizeof(p), TS, "N1", 3600, 5, "0.1.0") == 0);
    CHECK(payload_status(p, sizeof(p), TS, "N1", 3600, -128, "0.1.0") == 0);
    CHECK(payload_status(p, sizeof(p), TS, "N1", 2147483648UL, -61, "0.1.0") == 0);
    CHECK(payload_status(p, sizeof(p), 1727340000ULL, "N1", 3600, -61, "0.1.0") == 0);
}

// ------------------------------------------------------------ nRF24L01+

// A fake radio: a register file that answers SPI commands, a clock that only
// moves when the driver waits, and a record of everything the driver did.
// Any command that is not on the receive-only list fails the test.

#define MAX_EVENTS 4096

typedef enum { EV_CE_LOW, EV_CE_HIGH, EV_DELAY, EV_WRITE, EV_READ, EV_FLUSH_RX } event_kind_t;

typedef struct {
    event_kind_t kind;
    uint8_t reg;
    uint8_t value;
    uint32_t us;
} event_t;

typedef struct {
    uint8_t regs[32];
    bool ce;
    uint64_t now_us;
    uint64_t ce_high_at;
    uint8_t busy[SPECTRUM_CHANNELS];  // channels with a carrier on them
    int dead;                         // 0: present, 1: MISO reads 0xFF, 2: reads 0x00
    int forbidden;                    // commands outside the receive-only set
    int not_allowed;                  // writes the allow-list would refuse
    int written_while_listening;      // register writes with CE high
    int config_without_prim_rx;
    event_t events[MAX_EVENTS];
    int n_events;
} fake_radio_t;

static void fake_reset(fake_radio_t *f) {
    memset(f, 0, sizeof(*f));
    f->regs[NRF24_REG_CONFIG] = 0x08;  // reset values from the datasheet
    f->regs[NRF24_REG_EN_AA] = 0x3F;
    f->regs[NRF24_REG_RF_CH] = 0x02;
    f->regs[NRF24_REG_RF_SETUP] = 0x0F;
    f->regs[NRF24_REG_STATUS] = 0x0E;
}

static void fake_event(fake_radio_t *f, event_kind_t kind, uint8_t reg, uint8_t value, uint32_t us) {
    if (f->n_events < MAX_EVENTS) {
        f->events[f->n_events++] = (event_t){kind, reg, value, us};
    }
}

static void fake_transfer(void *ctx, const uint8_t *tx, uint8_t *rx, size_t len) {
    fake_radio_t *f = ctx;
    memset(rx, 0, len);
    if (f->dead) {
        memset(rx, f->dead == 1 ? 0xFF : 0x00, len);
        return;
    }
    uint8_t cmd = tx[0];
    rx[0] = f->regs[NRF24_REG_STATUS];
    if ((cmd & 0xE0) == NRF24_CMD_R_REGISTER && len == 2) {
        uint8_t reg = cmd & 0x1f;
        uint8_t value = f->regs[reg];
        if (reg == NRF24_REG_RPD) {
            uint8_t ch = f->regs[NRF24_REG_RF_CH] & 0x7f;
            bool settled = f->ce && f->now_us - f->ce_high_at >= NRF24_RPD_WAIT_US;
            value = (settled && ch < SPECTRUM_CHANNELS && f->busy[ch]) ? 1 : 0;
        }
        rx[1] = value;
        fake_event(f, EV_READ, reg, value, 0);
    } else if ((cmd & 0xE0) == NRF24_CMD_W_REGISTER && len == 2) {
        uint8_t reg = cmd & 0x1f;
        uint8_t value = tx[1];
        if (!nrf24_write_allowed(reg, value)) {
            f->not_allowed++;
        }
        if (f->ce) {
            f->written_while_listening++;
        }
        if (reg == NRF24_REG_CONFIG && !(value & NRF24_PRIM_RX)) {
            f->config_without_prim_rx++;
        }
        if (reg == NRF24_REG_STATUS) {
            f->regs[reg] &= (uint8_t)~value;  // write 1 to clear
        } else {
            f->regs[reg] = reg == NRF24_REG_RF_CH ? (value & 0x7f) : value;
        }
        fake_event(f, EV_WRITE, reg, value, 0);
    } else if (cmd == NRF24_CMD_FLUSH_RX && len == 1) {
        fake_event(f, EV_FLUSH_RX, 0, 0, 0);
    } else if (cmd == NRF24_CMD_NOP && len == 1) {
        // harmless
    } else {
        // W_TX_PAYLOAD (0xA0), W_ACK_PAYLOAD (0xA8..), W_TX_PAYLOAD_NO_ACK
        // (0xB0), REUSE_TX_PL (0xE3), FLUSH_TX (0xE1), R_RX_PAYLOAD (0x61),
        // or anything else: not part of a receive-only scanner.
        f->forbidden++;
    }
}

static void fake_set_ce(void *ctx, bool high) {
    fake_radio_t *f = ctx;
    if (high && !f->ce) {
        f->ce_high_at = f->now_us;
    }
    f->ce = high;
    fake_event(f, high ? EV_CE_HIGH : EV_CE_LOW, 0, 0, 0);
}

static void fake_delay(void *ctx, uint32_t us) {
    fake_radio_t *f = ctx;
    f->now_us += us;
    fake_event(f, EV_DELAY, 0, 0, us);
}

static fake_radio_t radio;
static const nrf24_hal_t fake_hal = {&radio, fake_transfer, fake_set_ce, fake_delay};

static void check_receive_only(const fake_radio_t *f) {
    CHECK(f->forbidden == 0);
    CHECK(f->not_allowed == 0);
    CHECK(f->written_while_listening == 0);
    CHECK(f->config_without_prim_rx == 0);
}

static void test_nrf_probe(void) {
    fake_reset(&radio);
    CHECK(nrf24_probe(&fake_hal));
    CHECK(!radio.ce);
    check_receive_only(&radio);

    fake_reset(&radio);
    radio.dead = 1;  // MISO floating high
    CHECK(!nrf24_probe(&fake_hal));

    fake_reset(&radio);
    radio.dead = 2;  // MISO stuck low
    CHECK(!nrf24_probe(&fake_hal));
}

static void test_nrf_start_rx(void) {
    fake_reset(&radio);
    CHECK(nrf24_start_rx(&fake_hal));
    CHECK(radio.regs[NRF24_REG_CONFIG] & NRF24_PRIM_RX);
    CHECK(radio.regs[NRF24_REG_CONFIG] & NRF24_PWR_UP);
    CHECK(radio.regs[NRF24_REG_EN_AA] == 0);
    CHECK((radio.regs[NRF24_REG_RF_SETUP] & (NRF24_CONT_WAVE | NRF24_PLL_LOCK)) == 0);
    CHECK(!radio.ce);
    check_receive_only(&radio);

    // EN_AA must be off before the radio is powered up in RX mode.
    int en_aa_at = -1, config_at = -1;
    for (int i = 0; i < radio.n_events; i++) {
        if (radio.events[i].kind == EV_WRITE && radio.events[i].reg == NRF24_REG_EN_AA && en_aa_at < 0) {
            en_aa_at = i;
        }
        if (radio.events[i].kind == EV_WRITE && radio.events[i].reg == NRF24_REG_CONFIG && config_at < 0) {
            config_at = i;
        }
    }
    CHECK(en_aa_at >= 0 && config_at > en_aa_at);

    fake_reset(&radio);
    radio.dead = 1;
    CHECK(!nrf24_start_rx(&fake_hal));
}

static void test_nrf_sweep(void) {
    fake_reset(&radio);
    CHECK(nrf24_start_rx(&fake_hal));
    radio.busy[2] = radio.busy[40] = radio.busy[41] = radio.busy[80] = radio.busy[125] = 1;
    radio.n_events = 0;

    uint8_t rpd[SPECTRUM_CHANNELS];
    memset(rpd, 0xAA, sizeof(rpd));
    nrf24_sweep(&fake_hal, rpd);
    for (int c = 0; c < SPECTRUM_CHANNELS; c++) {
        CHECK(rpd[c] == radio.busy[c]);
    }
    CHECK(!radio.ce);
    check_receive_only(&radio);

    // Each channel: CE low, write RF_CH, CE high, wait >= 170 us, read RPD, CE low.
    int i = 0;
    for (int c = 0; c < SPECTRUM_CHANNELS; c++) {
        CHECK(radio.events[i].kind == EV_CE_LOW);
        CHECK(radio.events[i + 1].kind == EV_WRITE && radio.events[i + 1].reg == NRF24_REG_RF_CH &&
              radio.events[i + 1].value == c);
        CHECK(radio.events[i + 2].kind == EV_CE_HIGH);
        CHECK(radio.events[i + 3].kind == EV_DELAY && radio.events[i + 3].us >= 170);
        CHECK(radio.events[i + 4].kind == EV_READ && radio.events[i + 4].reg == NRF24_REG_RPD);
        CHECK(radio.events[i + 5].kind == EV_CE_LOW);
        i += 6;
    }
    CHECK(i == radio.n_events);
}

static void test_nrf_write_allow_list(void) {
    CHECK(nrf24_write_allowed(NRF24_REG_CONFIG, NRF24_CONFIG_RX));
    CHECK(!nrf24_write_allowed(NRF24_REG_CONFIG, NRF24_PWR_UP));  // PRIM_RX clear means TX mode
    CHECK(!nrf24_write_allowed(NRF24_REG_CONFIG, 0x00));
    CHECK(nrf24_write_allowed(NRF24_REG_EN_AA, 0));
    CHECK(!nrf24_write_allowed(NRF24_REG_EN_AA, 0x3F));
    CHECK(nrf24_write_allowed(NRF24_REG_RF_CH, 125));
    CHECK(!nrf24_write_allowed(NRF24_REG_RF_CH, 126));
    CHECK(nrf24_write_allowed(NRF24_REG_RF_SETUP, NRF24_RF_SETUP_RX));
    CHECK(!nrf24_write_allowed(NRF24_REG_RF_SETUP, NRF24_CONT_WAVE));
    CHECK(!nrf24_write_allowed(NRF24_REG_RF_SETUP, NRF24_PLL_LOCK));
    CHECK(nrf24_write_allowed(NRF24_REG_STATUS, NRF24_STATUS_FLAGS));
    CHECK(!nrf24_write_allowed(NRF24_REG_STATUS, 0x01));
    CHECK(!nrf24_write_allowed(0x04, 0x00));  // SETUP_RETR: retransmit settings
    CHECK(!nrf24_write_allowed(0x10, 0x00));  // TX_ADDR
    CHECK(!nrf24_write_allowed(0x1C, 0x00));  // DYNPD
    CHECK(!nrf24_write_allowed(0x1D, 0x00));  // FEATURE: ack payloads
}

// --------------------------------------------------------------- samples

static void write_msg(FILE *f, const char *kind, const char *payload) {
    char topic[TOPIC_MAX_LEN];
    CHECK(payload_topic(topic, sizeof(topic), "N1", kind) > 0);
    CHECK(payload[0] == '{');
    fprintf(f, "msg\t%s\t%s\n", topic, payload);
}

static void write_hash(FILE *f, const char *salt, const uint8_t addr[ADDR_LEN]) {
    char hash[ADDR_HASH_LEN + 1];
    char salt_hex[2 * 128 + 1];
    char addr_hex[2 * ADDR_LEN + 1];
    CHECK(strlen(salt) <= 128);
    addr_hash(salt, addr, hash);
    to_hex((const uint8_t *)salt, strlen(salt), salt_hex);
    to_hex(addr, ADDR_LEN, addr_hex);
    fprintf(f, "hash\t%s\t%s\t%s\n", salt_hex, addr_hex, hash);
}

static int write_samples(const char *path) {
    FILE *f = fopen(path, "w");
    if (!f) {
        perror(path);
        return 1;
    }
    char p[PAYLOAD_BLE_MAX_LEN > PAYLOAD_SPECTRUM_MAX_LEN ? PAYLOAD_BLE_MAX_LEN : PAYLOAD_SPECTRUM_MAX_LEN];
    char hash[ADDR_HASH_LEN + 1];
    addr_hash("invigil-test-vector", VECTOR_ADDR, hash);

    // BLE: one reading, a mixed message, and a full message of worst-case readings.
    ble_batch_t b;
    const ble_reading_t r1 = ble_reading(TS, hash, -58, true, 0x004C);
    const ble_reading_t r2 = ble_reading(TS + 300, hash, -127, false, 0);
    const ble_reading_t r3 = ble_reading(CONTRACT_MAX_TS_MS, hash, 0, true, 0xFFFF);
    const ble_reading_t worst = ble_reading(CONTRACT_MAX_TS_MS, hash, -127, true, 0xFFFF);
    CHECK(ble_batch_begin(&b, p, sizeof(p), TS + 877, "N1"));
    CHECK(ble_batch_add(&b, &r1) == BLE_BATCH_ADDED);
    CHECK(ble_batch_finish(&b) > 0);
    write_msg(f, "ble", p);
    CHECK(ble_batch_begin(&b, p, sizeof(p), CONTRACT_MAX_TS_MS, "N1"));
    CHECK(ble_batch_add(&b, &r1) == BLE_BATCH_ADDED);
    CHECK(ble_batch_add(&b, &r2) == BLE_BATCH_ADDED);
    CHECK(ble_batch_add(&b, &r3) == BLE_BATCH_ADDED);
    CHECK(ble_batch_finish(&b) > 0);
    write_msg(f, "ble", p);
    CHECK(ble_batch_begin(&b, p, sizeof(p), CONTRACT_MAX_TS_MS, "N1"));
    while (ble_batch_add(&b, &worst) == BLE_BATCH_ADDED) {
    }
    CHECK(ble_batch_finish(&b) > 0);
    write_msg(f, "ble", p);

    // Spectrum
    spectrum_t s;
    spectrum_reset(&s);
    s.sweeps = 41;
    for (int c = 27; c < 48; c++) {
        s.hits[c] = 11;  // a Wi-Fi block around channel 6
    }
    s.hits[2] = 1;
    s.hits[80] = 41;
    CHECK(payload_spectrum(p, sizeof(p), TS, "N1", &s) > 0);
    write_msg(f, "spectrum", p);

    spectrum_reset(&s);
    s.sweeps = 1;
    CHECK(payload_spectrum(p, sizeof(p), TS, "N1", &s) > 0);
    write_msg(f, "spectrum", p);

    s.sweeps = SPECTRUM_MAX_SWEEPS;
    for (int c = 0; c < SPECTRUM_CHANNELS; c++) {
        s.hits[c] = SPECTRUM_MAX_SWEEPS;
    }
    CHECK(payload_spectrum(p, sizeof(p), CONTRACT_MAX_TS_MS, "N1", &s) > 0);
    write_msg(f, "spectrum", p);

    // Status
    CHECK(payload_status(p, sizeof(p), TS, "N1", 3600, -61, "0.1.0") > 0);
    write_msg(f, "status", p);
    CHECK(payload_status(p, sizeof(p), CONTRACT_MIN_TS_MS, "N1", CONTRACT_MAX_UPTIME_S, -127,
                         "0.1.0-plus-a-long-build-suffix") > 0);
    write_msg(f, "status", p);

    // Hash vectors for check_contract.py to compare with hash_addr(). The
    // salts cover empty, both sides of the 64-byte block edge, and UTF-8.
    static const uint8_t addrs[][ADDR_LEN] = {
        {0x01, 0x23, 0x45, 0x67, 0x89, 0xAB},
        {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF},
        {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
        {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF},
    };
    char a55[56], a58[59], a64[65];
    memset(a55, 'a', 55);
    a55[55] = '\0';
    memset(a58, 'a', 58);
    a58[58] = '\0';
    memset(a64, 'a', 64);
    a64[64] = '\0';
    const char *salts[] = {
        "invigil-test-vector", "", a55, a58, a64,
        "\xd8\xb3\xd8\xb1-salt",  // UTF-8, starts with an Arabic word
    };
    for (size_t s_i = 0; s_i < sizeof(salts) / sizeof(salts[0]); s_i++) {
        for (size_t a_i = 0; a_i < sizeof(addrs) / sizeof(addrs[0]); a_i++) {
            write_hash(f, salts[s_i], addrs[a_i]);
        }
    }

    fclose(f);
    return 0;
}

int main(int argc, char **argv) {
    test_sha256_standard_vectors();
    test_addr_hash_vector_both_orders();
    test_addr_hash_validity();
    test_company_id_found();
    test_company_id_absent();
    test_company_id_malformed();
    test_company_id_format();
    test_spectrum_counting();
    test_spectrum_caps_at_contract_max();
    test_ring_fifo_and_drop_oldest();
    test_topics();
    test_ble_batch();
    test_ble_batch_rejects_off_contract();
    test_ble_batch_size_limit();
    test_spectrum_payload();
    test_spectrum_payload_limits();
    test_status_payload();
    test_nrf_probe();
    test_nrf_start_rx();
    test_nrf_sweep();
    test_nrf_write_allow_list();

    if (argc > 1 && write_samples(argv[1]) != 0) {
        return 1;
    }

    printf("%d checks, %d failed\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
