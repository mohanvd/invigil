#include "ble_scan.h"

#include <stdio.h>
#include <string.h>

#include "config.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "host/ble_hs.h"
#include "host/util/util.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "psa/crypto.h"

static const char *TAG = "ble";

// Shared test vector. Same values as the README and server/tests/test_contract.py.
#define TEST_SALT          "invigil-test-vector"
#define TEST_HASH          "41239c0be85e"
#define TEST_HASH_REVERSED "5cebc32cde2c"  // what you get if val[] is not reversed
static const uint8_t TEST_VAL[6] = {0xAB, 0x89, 0x67, 0x45, 0x23, 0x01};  // 01:23:45:67:89:AB

// Room for about 3 s of advertisements from a dozen devices. Placeholder.
#define QUEUE_LEN 256

typedef struct {
    int64_t ts;
    char addr[ADDR_HASH_LEN + 1];
    int8_t rssi;
    int32_t mfr;  // Bluetooth SIG company ID, or -1 if the advertisement has none
} ble_reading_t;

static QueueHandle_t s_queue;
static volatile bool s_synced;
static volatile bool s_scanning;
static uint8_t s_own_addr_type;
static uint32_t s_overflow;

void ble_scan_hash_addr(const uint8_t val[6], const char *salt, char out[ADDR_HASH_LEN + 1])
{
    // Contract order: salt bytes, then the address most significant byte first.
    // NimBLE stores it least significant byte first, so reverse it.
    uint8_t addr[6];
    for (int i = 0; i < 6; i++) {
        addr[i] = val[5 - i];
    }

    uint8_t digest[32];
    size_t digest_len = 0;
    psa_hash_operation_t op = PSA_HASH_OPERATION_INIT;
    if (psa_crypto_init() != PSA_SUCCESS ||
        psa_hash_setup(&op, PSA_ALG_SHA_256) != PSA_SUCCESS ||
        psa_hash_update(&op, (const uint8_t *)salt, strlen(salt)) != PSA_SUCCESS ||
        psa_hash_update(&op, addr, sizeof(addr)) != PSA_SUCCESS ||
        psa_hash_finish(&op, digest, sizeof(digest), &digest_len) != PSA_SUCCESS) {
        // Never fall back to sending an unhashed address.
        psa_hash_abort(&op);
        ESP_LOGE(TAG, "SHA-256 failed");
        abort();
    }
    for (int i = 0; i < ADDR_HASH_LEN / 2; i++) {
        snprintf(out + 2 * i, 3, "%02x", digest[i]);
    }
}

bool ble_scan_self_test(void)
{
    char got[ADDR_HASH_LEN + 1];
    ble_scan_hash_addr(TEST_VAL, TEST_SALT, got);
    if (strcmp(got, TEST_HASH) == 0) {
        ESP_LOGI(TAG, "hash test vector PASS (%s)", got);
        return true;
    }
    if (strcmp(got, TEST_HASH_REVERSED) == 0) {
        ESP_LOGE(TAG, "hash test vector FAIL: got %s, the address byte order is backwards", got);
    } else {
        ESP_LOGE(TAG, "hash test vector FAIL: got %s, expected %s", got, TEST_HASH);
    }
    return false;
}

static int on_gap_event(struct ble_gap_event *event, void *arg)
{
    if (event->type != BLE_GAP_EVENT_DISC || !s_scanning) {
        return 0;  // outside a scan window: drop
    }
    const struct ble_gap_disc_desc *d = &event->disc;
    if (d->rssi > 0) {
        return 0;  // 127 means the controller had no RSSI for this packet
    }

    ble_reading_t r = {.ts = now_ms(), .rssi = d->rssi, .mfr = -1};
    ble_scan_hash_addr(d->addr.val, g_config.hash_salt, r.addr);

    struct ble_hs_adv_fields fields;
    if (ble_hs_adv_parse_fields(&fields, d->data, d->length_data) == 0 && fields.mfg_data_len >= 2) {
        r.mfr = fields.mfg_data[0] | (fields.mfg_data[1] << 8);  // little-endian company ID
    }
    if (xQueueSend(s_queue, &r, 0) != pdTRUE) {
        __atomic_fetch_add(&s_overflow, 1, __ATOMIC_RELAXED);
    }
    return 0;
}

static void on_sync(void)
{
    int rc = ble_hs_util_ensure_addr(0);
    if (rc == 0) {
        rc = ble_hs_id_infer_auto(0, &s_own_addr_type);
    }
    if (rc != 0) {
        ESP_LOGE(TAG, "no usable BLE address (rc=%d)", rc);
        return;
    }
    s_synced = true;
    ESP_LOGI(TAG, "NimBLE ready");
}

static void on_reset(int reason)
{
    s_synced = false;
    ESP_LOGW(TAG, "NimBLE reset (reason %d)", reason);
}

static void host_task(void *param)
{
    nimble_port_run();  // returns only when nimble_port_stop() is called
    nimble_port_freertos_deinit();
}

void ble_scan_init(void)
{
    s_queue = xQueueCreate(QUEUE_LEN, sizeof(ble_reading_t));
    ESP_ERROR_CHECK(s_queue ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(nimble_port_init());
    ble_hs_cfg.sync_cb = on_sync;
    ble_hs_cfg.reset_cb = on_reset;
    nimble_port_freertos_init(host_task);
}

bool ble_scan_start(void)
{
    if (!s_synced) {
        return false;
    }
    // Passive: the node only listens and never sends scan requests.
    // Interval equal to window means the receiver is on for the whole scan window.
    // filter_duplicates off: every advertisement counts for the RSSI fingerprint.
    const struct ble_gap_disc_params params = {
        .itvl = 0x30,    // 30 ms in 0.625 ms units
        .window = 0x30,
        .passive = 1,
        .filter_duplicates = 0,
    };
    s_scanning = true;
    const int rc = ble_gap_disc(s_own_addr_type, BLE_HS_FOREVER, &params, on_gap_event, NULL);
    if (rc != 0) {
        s_scanning = false;
        ESP_LOGW(TAG, "scan start failed (rc=%d)", rc);
        return false;
    }
    return true;
}

void ble_scan_stop(void)
{
    s_scanning = false;
    ble_gap_disc_cancel();
}

bool ble_scan_take_json(char *buf, size_t len)
{
    ble_reading_t r;
    if (xQueueReceive(s_queue, &r, 0) != pdTRUE) {
        return false;
    }
    char mfr[16] = "null";
    if (r.mfr >= 0) {
        snprintf(mfr, sizeof(mfr), "\"0x%04X\"", (unsigned)r.mfr);
    }
    snprintf(buf, len, "{\"ts\":%lld,\"node\":\"%s\",\"addr\":\"%s\",\"rssi\":%d,\"mfr\":%s}",
             (long long)r.ts, g_config.node_id, r.addr, r.rssi, mfr);
    return true;
}

uint32_t ble_scan_take_overflow(void)
{
    return __atomic_exchange_n(&s_overflow, 0, __ATOMIC_RELAXED);
}
