// Bounded buffer of BLE readings waiting for the next send window.
// When it is full, the oldest reading is dropped and counted.
//
// No locking here. On the unit, the BTstack callback pushes and the main loop
// pops, so every call must be made with the async context lock held.

#ifndef INVIGIL_BLE_RING_H
#define INVIGIL_BLE_RING_H

#include <stdbool.h>
#include <stdint.h>

#include "addr_hash.h"

typedef struct {
    uint64_t ts_ms;                // when the advertisement was heard, ms since epoch
    char addr[ADDR_HASH_LEN + 1];  // hashed address, never the raw one
    int8_t rssi;                   // dBm
    bool has_mfr;
    uint16_t mfr;                  // Bluetooth SIG company ID, valid if has_mfr
} ble_reading_t;

typedef struct {
    ble_reading_t *items;
    uint32_t capacity;
    uint32_t head;     // index of the oldest reading
    uint32_t count;
    uint32_t dropped;  // readings dropped because the buffer was full
} ble_ring_t;

void ble_ring_init(ble_ring_t *ring, ble_reading_t *storage, uint32_t capacity);
void ble_ring_push(ble_ring_t *ring, const ble_reading_t *reading);
bool ble_ring_peek(const ble_ring_t *ring, ble_reading_t *out);  // copies the oldest
// Copies the reading i places after the oldest (0 is the oldest). False past the end.
bool ble_ring_peek_at(const ble_ring_t *ring, uint32_t i, ble_reading_t *out);
void ble_ring_pop(ble_ring_t *ring);                              // removes the oldest

#endif
