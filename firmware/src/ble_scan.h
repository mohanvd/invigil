// Passive BLE scanning with NimBLE. Addresses are hashed the moment an
// advertisement arrives, so a raw address never leaves the NimBLE callback.

#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ADDR_HASH_LEN 12  // hex chars

// Salted SHA-256 of a NimBLE address, first 12 hex chars (see docs/contract.md).
// val is ble_addr_t.val, least significant byte first. out needs 13 bytes.
void ble_scan_hash_addr(const uint8_t val[6], const char *salt, char out[ADDR_HASH_LEN + 1]);

// Checks ble_scan_hash_addr against the shared test vector in the README.
// Logs PASS or FAIL and returns true on PASS.
bool ble_scan_self_test(void);

// Starts the NimBLE host. Scanning only runs between ble_scan_start() and ble_scan_stop().
void ble_scan_init(void);

// Starts a scan window. Returns false if NimBLE is not ready yet.
bool ble_scan_start(void);

// Ends the scan window. Advertisements that arrive after this are dropped.
void ble_scan_stop(void);

// Takes the oldest queued reading as contract JSON. Returns false when the queue is empty.
bool ble_scan_take_json(char *buf, size_t len);

// Readings lost because the queue was full, since the last call.
uint32_t ble_scan_take_overflow(void);
