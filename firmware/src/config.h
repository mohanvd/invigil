// Node settings: secrets from secrets.h plus fixed timing constants.

#pragma once

#include <stdbool.h>
#include <stdint.h>
#include <sys/time.h>

// Scan and send windows alternate so the node never scans while it transmits
// over Wi-Fi (MQTT contract). Placeholders until measured on a real node.
#define SCAN_WINDOW_MS      800
#define SEND_WINDOW_MS      200
// Minimum quiet time after the last publish, so Wi-Fi frames still queued in
// the driver go out before scanning restarts. Placeholder, measure it.
#define SEND_GUARD_MS       20
#define STATUS_INTERVAL_MS  10000

// Timestamps before this mean NTP has not set the clock yet (logger rejects them).
#define MIN_VALID_TS_MS     1600000000000LL

typedef struct {
    const char *wifi_ssid;
    const char *wifi_password;
    const char *mqtt_uri;
    const char *mqtt_username;
    const char *mqtt_password;
    const char *node_id;
    const char *hash_salt;
    const char *ntp_server;
} node_config_t;

extern const node_config_t g_config;

// Logs anything wrong with secrets.h. Returns false if the node cannot run.
bool config_check(void);

// Wall clock time in ms since epoch. Only meaningful after NTP sync (wifi_sta).
static inline int64_t now_ms(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}
