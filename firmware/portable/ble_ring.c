#include "ble_ring.h"

void ble_ring_init(ble_ring_t *ring, ble_reading_t *storage, uint32_t capacity) {
    ring->items = storage;
    ring->capacity = capacity;
    ring->head = 0;
    ring->count = 0;
    ring->dropped = 0;
}

void ble_ring_push(ble_ring_t *ring, const ble_reading_t *reading) {
    if (ring->capacity == 0) {
        ring->dropped++;
        return;
    }
    if (ring->count == ring->capacity) {
        ring->head = (ring->head + 1) % ring->capacity;
        ring->count--;
        ring->dropped++;
    }
    ring->items[(ring->head + ring->count) % ring->capacity] = *reading;
    ring->count++;
}

bool ble_ring_peek(const ble_ring_t *ring, ble_reading_t *out) {
    return ble_ring_peek_at(ring, 0, out);
}

bool ble_ring_peek_at(const ble_ring_t *ring, uint32_t i, ble_reading_t *out) {
    if (i >= ring->count) {
        return false;
    }
    *out = ring->items[(ring->head + i) % ring->capacity];
    return true;
}

void ble_ring_pop(ble_ring_t *ring) {
    if (ring->count == 0) {
        return;
    }
    ring->head = (ring->head + 1) % ring->capacity;
    ring->count--;
}
