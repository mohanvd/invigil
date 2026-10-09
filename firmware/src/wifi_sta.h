// Wi-Fi station and SNTP clock.

#ifndef INVIGIL_WIFI_STA_H
#define INVIGIL_WIFI_STA_H

#include <stdbool.h>
#include <stdint.h>

// Turns on station mode. Call once, after cyw43_arch_init_with_country().
void wifi_sta_init(void);

// Connects, notices a dropped link and reconnects with backoff, and starts
// SNTP once connected. Call from the main loop, never inside a scan window,
// because a connection attempt transmits.
void wifi_sta_poll(void);

bool wifi_sta_up(void);
const char *wifi_sta_state_name(void);

// True once SNTP has set the clock. Nothing is published before that,
// because the contract rejects unsynced timestamps.
bool wifi_sta_time_synced(void);

// Milliseconds since the epoch: SNTP offset + time_us_64(). Only meaningful
// once wifi_sta_time_synced() is true.
uint64_t wifi_sta_time_ms(void);

// Wi-Fi signal strength in dBm, clamped to -127..0 for the status message.
// -127 if it cannot be read.
int wifi_sta_rssi(void);

// Frames lwIP has handed to the radio since boot. Comparing it before and
// after a sweep shows whether lwIP sent anything during that sweep. Frames
// the radio firmware sends on its own (802.11 acks, power-save frames) are
// not counted.
uint32_t wifi_sta_tx_frames(void);

#endif
