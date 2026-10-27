#include "ble_scan.h"

#include <stdio.h>
#include <string.h>

#include "btstack.h"
#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"

#include "addr_hash.h"
#include "adv_data.h"
#include "config.h"
#include "wifi_sta.h"

// Test vector from docs/hashing.md. The address and salt are made up.
static const char TEST_SALT[] = "invigil-test-vector";
static const char TEST_ADDR[] = "01:23:45:67:89:AB";
static const char TEST_HASH[] = "41239c0be85e";
static const char TEST_HASH_REVERSED[] = "5cebc32cde2c";

// HCI LE Advertising Report: 127 means the controller has no RSSI.
#define RSSI_NOT_AVAILABLE 127

static btstack_packet_callback_registration_t hci_callback;
static ble_reading_t storage[BLE_BUFFER_SIZE];
static ble_ring_t ring;
static bool check_passed;

// Shared between the BTstack callback and the main loop. Read and written
// with the async context lock held.
static bool hci_working;
static bool in_scan_window;
static uint32_t captured;
static uint32_t no_rssi;
static uint32_t dropped_reported;

// The one place a Bluetooth address becomes a hash. Scan reports and the
// boot self-check both go through it, so the self-check tests the real path.
// bd_addr_t holds the bytes in the order BTstack prints them.
static void hash_bd_addr(const char *salt, const bd_addr_t addr, char out[ADDR_HASH_LEN + 1]) {
    addr_hash(salt, addr, out);
}

#if INVIGIL_DEBUG_RAW_ADDR
// Byte-order check only (docs/firmware.md). Prints each device at most once
// every 5 s. The table remembers hashes, never raw addresses.
#define DEBUG_SLOTS 32
#define DEBUG_REPEAT_MS 5000
static struct {
    char hash[ADDR_HASH_LEN + 1];
    uint32_t at_ms;
} debug_seen[DEBUG_SLOTS];

static void debug_print_raw(const bd_addr_t addr, const char *hash, int rssi) {
    uint32_t now = to_ms_since_boot(get_absolute_time());
    int slot = 0;
    for (int i = 0; i < DEBUG_SLOTS; i++) {
        if (strcmp(debug_seen[i].hash, hash) == 0) {
            if (now - debug_seen[i].at_ms < DEBUG_REPEAT_MS) {
                return;
            }
            slot = i;
            break;
        }
        if (debug_seen[i].at_ms < debug_seen[slot].at_ms) {
            slot = i;
        }
    }
    strcpy(debug_seen[slot].hash, hash);
    debug_seen[slot].at_ms = now;
    printf("debug: raw %s -> hash %s, rssi %d\n", bd_addr_to_str(addr), hash, rssi);
}
#endif

static void on_advertisement(const uint8_t *packet) {
    if (!in_scan_window || !check_passed || !wifi_sta_time_synced()) {
        return;
    }
    int rssi = gap_event_advertising_report_get_rssi(packet);
    if (rssi == RSSI_NOT_AVAILABLE) {
        no_rssi++;
        return;
    }
    // The controller may report up to +20 dBm. The contract allows -127..0.
    if (rssi > 0) {
        rssi = 0;
    }
    if (rssi < -127) {
        rssi = -127;
    }

    ble_reading_t r;
    memset(&r, 0, sizeof(r));
    r.ts_ms = wifi_sta_time_ms();
    r.rssi = (int8_t)rssi;
    r.has_mfr = adv_find_company_id(gap_event_advertising_report_get_data(packet),
                                    gap_event_advertising_report_get_data_length(packet), &r.mfr);

    bd_addr_t addr;
    gap_event_advertising_report_get_address(packet, addr);
    hash_bd_addr(HASH_SALT, addr, r.addr);
#if INVIGIL_DEBUG_RAW_ADDR
    debug_print_raw(addr, r.addr, rssi);
#endif
    memset(addr, 0, sizeof(addr));

    ble_ring_push(&ring, &r);
    captured++;
}

static void on_hci_event(uint8_t packet_type, uint16_t channel, uint8_t *packet, uint16_t size) {
    (void)channel;
    (void)size;
    if (packet_type != HCI_EVENT_PACKET) {
        return;
    }
    switch (hci_event_packet_get_type(packet)) {
    case BTSTACK_EVENT_STATE:
        hci_working = btstack_event_state_get_state(packet) == HCI_STATE_WORKING;
        if (hci_working && in_scan_window) {
            gap_start_scan();  // a scan window began before the controller was ready
        }
        break;
    case GAP_EVENT_ADVERTISING_REPORT:
        on_advertisement(packet);
        break;
    default:
        break;
    }
}

static bool self_check(void) {
    bd_addr_t addr;
    char hash[ADDR_HASH_LEN + 1];

    bool vector_ok = false;
    if (sscanf_bd_addr(TEST_ADDR, addr)) {
        hash_bd_addr(TEST_SALT, addr, hash);
        vector_ok = strcmp(hash, TEST_HASH) == 0;
        printf("  %s  hash test vector: got %s, expected %s\n", vector_ok ? "PASS" : "FAIL", hash, TEST_HASH);
        if (strcmp(hash, TEST_HASH_REVERSED) == 0) {
            printf("        the address bytes are reversed before hashing\n");
        }
    } else {
        printf("  FAIL  hash test vector: BTstack could not parse %s\n", TEST_ADDR);
    }

    bool salt_set = HASH_SALT[0] != '\0';
    bool salt_ok = salt_set && strcmp(HASH_SALT, TEST_SALT) != 0;
    printf("  %s  hash salt: %s\n", salt_ok ? "PASS" : "FAIL",
           salt_ok    ? "set"
           : salt_set ? "HASH_SALT is the test-vector salt, pick a secret one"
                      : "HASH_SALT is empty in firmware/secrets.h");
    return vector_ok && salt_ok;
}

bool ble_scan_init(void) {
    ble_ring_init(&ring, storage, BLE_BUFFER_SIZE);
#if INVIGIL_DEBUG_RAW_ADDR
    printf("  WARNING  debug build: raw Bluetooth addresses are printed on USB serial.\n"
           "           Use it only for the byte-order check, never in an exam.\n");
#endif
    check_passed = self_check();
    if (!check_passed) {
        printf("        BLE stays off and no BLE reading will be published\n");
        return false;
    }

    async_context_t *context = cyw43_arch_async_context();
    async_context_acquire_lock_blocking(context);
    hci_callback.callback = on_hci_event;
    hci_add_event_handler(&hci_callback);
    gap_set_scan_params(0 /* passive */, BLE_SCAN_INTERVAL, BLE_SCAN_WINDOW, 0 /* all devices */);
    gap_set_scan_duplicate_filter(false);  // the models need every advertisement
    hci_power_control(HCI_POWER_ON);
    async_context_release_lock(context);
    return true;
}

void ble_scan_start(void) {
    if (!check_passed) {
        return;
    }
    async_context_t *context = cyw43_arch_async_context();
    async_context_acquire_lock_blocking(context);
    in_scan_window = true;
    if (hci_working) {
        gap_start_scan();
    }
    async_context_release_lock(context);
}

void ble_scan_stop(void) {
    if (!check_passed) {
        return;
    }
    async_context_t *context = cyw43_arch_async_context();
    async_context_acquire_lock_blocking(context);
    in_scan_window = false;  // reports still in flight are dropped from here on
    if (hci_working) {
        gap_stop_scan();
    }
    async_context_release_lock(context);
}

bool ble_scan_peek_at_locked(uint32_t i, ble_reading_t *out) {
    return ble_ring_peek_at(&ring, i, out);
}

void ble_scan_pop_locked(void) {
    ble_ring_pop(&ring);
}

ble_scan_counts_t ble_scan_take_counts(void) {
    ble_scan_counts_t counts;
    async_context_t *context = cyw43_arch_async_context();
    async_context_acquire_lock_blocking(context);
    counts.captured = captured;
    counts.no_rssi = no_rssi;
    counts.dropped = ring.dropped - dropped_reported;
    counts.buffered = ring.count;
    captured = 0;
    no_rssi = 0;
    dropped_reported = ring.dropped;
    async_context_release_lock(context);
    return counts;
}
