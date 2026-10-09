// Per-channel hit counts for one scan window of the nRF24L01 sweep.

#ifndef INVIGIL_SPECTRUM_H
#define INVIGIL_SPECTRUM_H

#include <stdbool.h>
#include <stdint.h>

// nRF24L01 channels 0..125, channel c is 2400 + c MHz (NUM_CHANNELS in server/contract.py).
#define SPECTRUM_CHANNELS 126
// The contract allows 1..65535 sweeps per message.
#define SPECTRUM_MAX_SWEEPS 65535

typedef struct {
    uint32_t sweeps;  // complete sweeps counted in this window
    uint16_t hits[SPECTRUM_CHANNELS];
} spectrum_t;

void spectrum_reset(spectrum_t *s);

// Adds one complete sweep. rpd[c] is nonzero when channel c had a carrier
// above the RPD threshold. Returns false, and ignores the sweep, once the
// window already holds SPECTRUM_MAX_SWEEPS.
bool spectrum_add_sweep(spectrum_t *s, const uint8_t rpd[SPECTRUM_CHANNELS]);

#endif
