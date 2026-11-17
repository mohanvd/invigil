// Finds the broker by listening for the launcher's UDP beacon
// (portable/beacon.h, docs/firmware.md). Receive only: it never sends.

#ifndef INVIGIL_BROKER_FIND_H
#define INVIGIL_BROKER_FIND_H

#include <stdbool.h>
#include <stdint.h>

#include "lwip/ip_addr.h"

// Starts listening. Call once, after cyw43_arch_init_with_country().
// Returns false if lwIP could not open the UDP port.
bool broker_find_init(void);

// The laptop whose beacon is being heard right now.
bool broker_find_live(ip_addr_t *ip, uint16_t *port);
// The last laptop a beacon was heard from, however long ago.
bool broker_find_last(ip_addr_t *ip, uint16_t *port);

typedef struct {
    uint32_t heard;     // beacons with a good signature
    uint32_t rejected;  // datagrams on the beacon port that failed the check
} broker_find_counts_t;

// Counts since the last call.
broker_find_counts_t broker_find_take_counts(void);

#endif
