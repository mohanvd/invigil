// BLE scanner: BTstack observer, passive scan, duplicate filtering off.
// Every advertisement becomes one reading: hashed address, RSSI,
// manufacturer company ID and the time it was heard.

#ifndef INVIGIL_BLE_SCAN_H
#define INVIGIL_BLE_SCAN_H

#include <stdbool.h>
#include <stdint.h>

#include "ble_ring.h"

typedef struct {
    uint32_t captured;  // readings added to the buffer
    uint32_t dropped;   // oldest readings dropped because the buffer was full
    uint32_t no_rssi;   // reports skipped because the controller gave no RSSI
    uint32_t buffered;  // readings waiting now
} ble_scan_counts_t;

// Runs the boot self-check (hash test vector and salt), then sets up BTstack
// and powers on the Bluetooth controller. Returns false if the self-check
// failed. BLE stays off then, and no BLE reading is ever published.
bool ble_scan_init(void);

// Scan window start and end. No-ops if the self-check failed.
void ble_scan_start(void);
void ble_scan_stop(void);

// Buffer access for the send window. Call with the async context lock held
// (cyw43_arch_lwip_begin), since the BTstack callback adds readings.
// i counts from the oldest reading (0). Pop removes the oldest.
bool ble_scan_peek_at_locked(uint32_t i, ble_reading_t *out);
void ble_scan_pop_locked(void);

// Counts since the last call, plus the number buffered now.
ble_scan_counts_t ble_scan_take_counts(void);

#endif
