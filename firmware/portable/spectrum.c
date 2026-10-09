#include "spectrum.h"

#include <string.h>

void spectrum_reset(spectrum_t *s) {
    memset(s, 0, sizeof(*s));
}

bool spectrum_add_sweep(spectrum_t *s, const uint8_t rpd[SPECTRUM_CHANNELS]) {
    if (s->sweeps >= SPECTRUM_MAX_SWEEPS) {
        return false;
    }
    s->sweeps++;
    for (int c = 0; c < SPECTRUM_CHANNELS; c++) {
        if (rpd[c]) {
            s->hits[c]++;  // cannot pass sweeps, so it fits in 16 bits
        }
    }
    return true;
}
