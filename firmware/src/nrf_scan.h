// 2.4 GHz channel scanner: nRF24L01+PA+LNA on SPI0, receive only.
// Sweeps channels 0..125 and counts RPD hits per scan window.

#ifndef INVIGIL_NRF_SCAN_H
#define INVIGIL_NRF_SCAN_H

#include <stdbool.h>
#include <stdint.h>

#include "spectrum.h"

// Sets up SPI0 and the pins, checks the radio answers, and starts RX mode.
// Prints PASS or FAIL. Returns false if the radio is missing or did not take
// its settings; the unit then keeps BLE running and sends no spectrum messages.
bool nrf_scan_init(void);

void nrf_scan_begin_window(void);

// Runs one full sweep into a scratch buffer and returns how long it took in us.
// The sweep only counts once nrf_scan_keep_sweep() is called, so the caller
// can drop a sweep that overlapped a Wi-Fi transmission.
uint32_t nrf_scan_sweep(void);
void nrf_scan_keep_sweep(void);

// CE low (standby, not listening) and RX FIFO flushed. Call when the scan window ends.
void nrf_scan_end_window(void);

// Sweeps and hit counts for the current window.
const spectrum_t *nrf_scan_window(void);

#endif
