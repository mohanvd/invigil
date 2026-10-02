#include "wifi_sta.h"

#include <string.h>

#include "config.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_wifi.h"

static const char *TAG = "wifi";

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        const wifi_event_sta_disconnected_t *e = data;
        ESP_LOGW(TAG, "disconnected from \"%s\" (reason %d), retrying", g_config.wifi_ssid, e->reason);
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        const ip_event_got_ip_t *e = data;
        ESP_LOGI(TAG, "connected to \"%s\", IP " IPSTR, g_config.wifi_ssid, IP2STR(&e->ip_info.ip));
        // Sync the clock as soon as there is a network, and again after every reconnect.
        esp_netif_sntp_start();
    }
}

void wifi_sta_start(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL));

    wifi_config_t cfg = {0};
    strlcpy((char *)cfg.sta.ssid, g_config.wifi_ssid, sizeof(cfg.sta.ssid));
    strlcpy((char *)cfg.sta.password, g_config.wifi_password, sizeof(cfg.sta.password));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &cfg));

    esp_sntp_config_t sntp = ESP_NETIF_SNTP_DEFAULT_CONFIG(g_config.ntp_server);
    sntp.start = false;  // started on IP_EVENT_STA_GOT_IP
    ESP_ERROR_CHECK(esp_netif_sntp_init(&sntp));

    ESP_ERROR_CHECK(esp_wifi_start());
}

bool wifi_sta_wait_for_time(uint32_t timeout_ms)
{
    if (now_ms() >= MIN_VALID_TS_MS) {
        return true;
    }
    return esp_netif_sntp_sync_wait(pdMS_TO_TICKS(timeout_ms)) == ESP_OK && now_ms() >= MIN_VALID_TS_MS;
}

int wifi_sta_rssi(void)
{
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) != ESP_OK || ap.rssi > 0) {
        return -127;
    }
    return ap.rssi;
}
