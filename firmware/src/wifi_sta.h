// Wi-Fi station with automatic reconnect, plus NTP for real timestamps.

#pragma once

#include <stdbool.h>
#include <stdint.h>

// Starts Wi-Fi and NTP. Returns at once; connecting happens in the background.
void wifi_sta_start(void);

// Waits until NTP has set the clock. Returns false on timeout.
bool wifi_sta_wait_for_time(uint32_t timeout_ms);

// Access point signal strength in dBm (-127 to 0). -127 when not connected.
int wifi_sta_rssi(void);
