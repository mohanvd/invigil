#include "config.h"

#include <string.h>

#include "esp_log.h"

#if !__has_include("secrets.h")
#error "Missing src/secrets.h. Copy src/secrets.h.example to src/secrets.h and fill it in."
#endif
#include "secrets.h"

#ifndef INVIGIL_NTP_SERVER
#define INVIGIL_NTP_SERVER "pool.ntp.org"
#endif

// Empty values are caught at build time, before anything is flashed.
_Static_assert(sizeof(INVIGIL_WIFI_SSID) > 1, "INVIGIL_WIFI_SSID is empty in secrets.h");
_Static_assert(sizeof(INVIGIL_MQTT_URI) > 1, "INVIGIL_MQTT_URI is empty in secrets.h");
_Static_assert(sizeof(INVIGIL_HASH_SALT) > 1, "INVIGIL_HASH_SALT is empty in secrets.h");

static const char *TAG = "config";

const node_config_t g_config = {
    .wifi_ssid = INVIGIL_WIFI_SSID,
    .wifi_password = INVIGIL_WIFI_PASSWORD,
    .mqtt_uri = INVIGIL_MQTT_URI,
    .mqtt_username = INVIGIL_MQTT_USERNAME,
    .mqtt_password = INVIGIL_MQTT_PASSWORD,
    .node_id = INVIGIL_NODE_ID,
    .hash_salt = INVIGIL_HASH_SALT,
    .ntp_server = INVIGIL_NTP_SERVER,
};

bool config_check(void)
{
    const char *id = g_config.node_id;
    if (strcmp(id, "N1") != 0 && strcmp(id, "N2") != 0 && strcmp(id, "N3") != 0) {
        ESP_LOGE(TAG, "INVIGIL_NODE_ID must be \"N1\", \"N2\" or \"N3\"");
        return false;
    }
    return true;
}
