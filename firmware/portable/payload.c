#include "payload.h"

#include <string.h>

#include "addr_hash.h"
#include "adv_data.h"

// Small JSON writer. Keeps one byte free for the terminating NUL and marks
// the whole message failed if anything does not fit.
typedef struct {
    char *buf;
    size_t cap;
    size_t len;
    bool ok;
} writer_t;

static writer_t writer(char *buf, size_t cap) {
    writer_t w = {buf, cap, 0, cap > 0};
    return w;
}

static void put_char(writer_t *w, char c) {
    if (!w->ok || w->len + 1 >= w->cap) {
        w->ok = false;
        return;
    }
    w->buf[w->len++] = c;
}

static void put_raw(writer_t *w, const char *s) {
    while (*s) {
        put_char(w, *s++);
    }
}

static void put_u64(writer_t *w, uint64_t v) {
    char digits[20];
    int n = 0;
    do {
        digits[n++] = (char)('0' + v % 10);
        v /= 10;
    } while (v > 0);
    while (n > 0) {
        put_char(w, digits[--n]);
    }
}

static void put_int(writer_t *w, int v) {
    if (v < 0) {
        put_char(w, '-');
        put_u64(w, (uint64_t)(-(int64_t)v));
    } else {
        put_u64(w, (uint64_t)v);
    }
}

static void put_string(writer_t *w, const char *s) {
    static const char hex[] = "0123456789abcdef";
    put_char(w, '"');
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') {
            put_char(w, '\\');
            put_char(w, (char)c);
        } else if (c < 0x20) {
            put_raw(w, "\\u00");
            put_char(w, hex[c >> 4]);
            put_char(w, hex[c & 0xf]);
        } else {
            put_char(w, (char)c);
        }
    }
    put_char(w, '"');
}

static size_t finish(writer_t *w) {
    if (!w->ok) {
        if (w->cap > 0) {
            w->buf[0] = '\0';
        }
        return 0;
    }
    w->buf[w->len] = '\0';
    return w->len;
}

static size_t fail(char *buf, size_t cap) {
    if (cap > 0) {
        buf[0] = '\0';
    }
    return 0;
}

// "ts" and "node" open every payload.
static bool put_head(writer_t *w, uint64_t ts_ms, const char *node) {
    if (ts_ms < CONTRACT_MIN_TS_MS || ts_ms > CONTRACT_MAX_TS_MS || !payload_node_is_valid(node)) {
        return false;
    }
    put_raw(w, "{\"ts\":");
    put_u64(w, ts_ms);
    put_raw(w, ",\"node\":");
    put_string(w, node);
    return true;
}

static bool rssi_in_range(int rssi) {
    return rssi >= CONTRACT_MIN_RSSI && rssi <= CONTRACT_MAX_RSSI;
}

bool payload_node_is_valid(const char *node) {
    size_t len = strlen(node);
    if (len < 1 || len > 16) {
        return false;
    }
    for (size_t i = 0; i < len; i++) {
        char c = node[i];
        bool ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
                  c == '-' || c == '_';
        if (!ok) {
            return false;
        }
    }
    return true;
}

size_t payload_topic(char *buf, size_t cap, const char *node, const char *kind) {
    bool known = strcmp(kind, "ble") == 0 || strcmp(kind, "spectrum") == 0 || strcmp(kind, "status") == 0;
    if (!known || !payload_node_is_valid(node)) {
        return fail(buf, cap);
    }
    writer_t w = writer(buf, cap);
    put_raw(&w, "invigil/node/");
    put_raw(&w, node);
    put_char(&w, '/');
    put_raw(&w, kind);
    return finish(&w);
}

// The longest reading: {"ts":9999999999999,"addr":"...","rssi":-127,"mfr":"0xFFFF"}
// is 69 bytes. Room to spare.
#define READING_MAX_LEN 96
static const char BATCH_TAIL[] = "]}";

bool ble_batch_begin(ble_batch_t *b, char *buf, size_t cap, uint64_t ts_ms, const char *node) {
    b->buf = buf;
    b->limit = cap > 0 ? cap - 1 : 0;
    if (b->limit > CONTRACT_MAX_BLE_PAYLOAD) {
        b->limit = CONTRACT_MAX_BLE_PAYLOAD;
    }
    b->len = 0;
    b->count = 0;
    writer_t w = writer(buf, cap);
    if (!put_head(&w, ts_ms, node)) {
        fail(buf, cap);
        return false;
    }
    put_raw(&w, ",\"readings\":[");
    if (!w.ok || w.len + strlen(BATCH_TAIL) > b->limit) {
        fail(buf, cap);
        return false;
    }
    b->len = w.len;
    return true;
}

ble_batch_result_t ble_batch_add(ble_batch_t *b, const ble_reading_t *r) {
    // The address must already be a hash. A raw address in any printed form
    // fails this check, so it can never be published by mistake.
    if (r->ts_ms < CONTRACT_MIN_TS_MS || r->ts_ms > CONTRACT_MAX_TS_MS ||
        !addr_hash_is_valid(r->addr, strlen(r->addr)) || !rssi_in_range(r->rssi)) {
        return BLE_BATCH_INVALID;
    }
    char tmp[READING_MAX_LEN];
    writer_t w = writer(tmp, sizeof(tmp));
    put_raw(&w, "{\"ts\":");
    put_u64(&w, r->ts_ms);
    put_raw(&w, ",\"addr\":");
    put_string(&w, r->addr);
    put_raw(&w, ",\"rssi\":");
    put_int(&w, r->rssi);
    put_raw(&w, ",\"mfr\":");
    if (r->has_mfr) {
        char id[7];
        adv_format_company_id(r->mfr, id);
        put_string(&w, id);
    } else {
        put_raw(&w, "null");
    }
    put_char(&w, '}');
    if (!w.ok) {
        return BLE_BATCH_INVALID;
    }

    size_t comma = b->count > 0 ? 1 : 0;
    if (b->len + comma + w.len + strlen(BATCH_TAIL) > b->limit) {
        // In an empty message it can never fit, so do not ask for another.
        return b->count > 0 ? BLE_BATCH_FULL : BLE_BATCH_INVALID;
    }
    if (comma) {
        b->buf[b->len++] = ',';
    }
    memcpy(b->buf + b->len, tmp, w.len);
    b->len += w.len;
    b->count++;
    return BLE_BATCH_ADDED;
}

size_t ble_batch_finish(ble_batch_t *b) {
    if (b->count == 0) {
        b->buf[0] = '\0';
        return 0;
    }
    memcpy(b->buf + b->len, BATCH_TAIL, sizeof(BATCH_TAIL));  // with the NUL
    return b->len + strlen(BATCH_TAIL);
}

size_t payload_spectrum(char *buf, size_t cap, uint64_t ts_ms, const char *node,
                        const spectrum_t *spectrum) {
    if (spectrum->sweeps < 1 || spectrum->sweeps > SPECTRUM_MAX_SWEEPS) {
        return fail(buf, cap);
    }
    for (int c = 0; c < SPECTRUM_CHANNELS; c++) {
        if (spectrum->hits[c] > spectrum->sweeps) {
            return fail(buf, cap);
        }
    }
    writer_t w = writer(buf, cap);
    if (!put_head(&w, ts_ms, node)) {
        return fail(buf, cap);
    }
    put_raw(&w, ",\"sweeps\":");
    put_u64(&w, spectrum->sweeps);
    put_raw(&w, ",\"hits\":[");
    for (int c = 0; c < SPECTRUM_CHANNELS; c++) {
        if (c > 0) {
            put_char(&w, ',');
        }
        put_u64(&w, spectrum->hits[c]);
    }
    put_raw(&w, "]}");
    return finish(&w);
}

size_t payload_status(char *buf, size_t cap, uint64_t ts_ms, const char *node, uint32_t uptime_s,
                      int wifi_rssi, const char *fw) {
    size_t fw_len = strlen(fw);
    if (uptime_s > CONTRACT_MAX_UPTIME_S || !rssi_in_range(wifi_rssi) || fw_len < 1 ||
        fw_len > CONTRACT_MAX_FW_LEN) {
        return fail(buf, cap);
    }
    writer_t w = writer(buf, cap);
    if (!put_head(&w, ts_ms, node)) {
        return fail(buf, cap);
    }
    put_raw(&w, ",\"uptime_s\":");
    put_u64(&w, uptime_s);
    put_raw(&w, ",\"wifi_rssi\":");
    put_int(&w, wifi_rssi);
    put_raw(&w, ",\"fw\":");
    put_string(&w, fw);
    put_char(&w, '}');
    return finish(&w);
}
