// Invigil sensor node: passive BLE scanning, published over MQTT.
//
// The main loop alternates two windows, as the MQTT contract requires:
//   scan window: radios listen, nothing is published
//   send window: scanning is off, queued readings and status are published

#include "ble_scan.h"
#include "config.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mqtt_link.h"
#include "nvs_flash.h"
#include "wifi_sta.h"

static const char *TAG = "node";

static void init_nvs(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

static void wait_ms(int64_t ms)
{
    if (ms > 0) {
        vTaskDelay(pdMS_TO_TICKS(ms));
    }
}

static void run_windows(void)
{
    char json[160];
    uint32_t sent = 0, offline = 0;
    int64_t next_report_us = esp_timer_get_time() + 10 * 1000000LL;

    for (;;) {
        // Scan window.
        const bool scanning = ble_scan_start();
        wait_ms(SCAN_WINDOW_MS);
        if (scanning) {
            ble_scan_stop();
        }

        // Send window.
        const int64_t send_start_us = esp_timer_get_time();
        while (ble_scan_take_json(json, sizeof(json))) {
            if (mqtt_link_publish("ble", json)) {
                sent++;
            } else {
                offline++;
            }
        }
        mqtt_link_status_if_due();
        const int64_t used_ms = (esp_timer_get_time() - send_start_us) / 1000;
        wait_ms(used_ms + SEND_GUARD_MS > SEND_WINDOW_MS ? SEND_GUARD_MS : SEND_WINDOW_MS - used_ms);

        if (esp_timer_get_time() >= next_report_us) {
            ESP_LOGI(TAG, "last 10 s: %lu ble sent, %lu dropped offline, %lu dropped queue full%s",
                     (unsigned long)sent, (unsigned long)offline, (unsigned long)ble_scan_take_overflow(),
                     mqtt_link_connected() ? "" : " (broker not connected)");
            sent = offline = 0;
            next_report_us += 10 * 1000000LL;
        }
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "Invigil node %s, firmware %s", g_config.node_id, esp_app_get_description()->version);
    ble_scan_self_test();
    if (!config_check()) {
        ESP_LOGE(TAG, "fix secrets.h, then build and flash again");
        return;
    }

    init_nvs();
    wifi_sta_start();
    mqtt_link_start();
    ble_scan_init();

    // Readings without a real timestamp would be rejected by the logger.
    ESP_LOGI(TAG, "waiting for NTP time from %s", g_config.ntp_server);
    while (!wifi_sta_wait_for_time(10000)) {
        ESP_LOGW(TAG, "no time from %s yet", g_config.ntp_server);
    }
    ESP_LOGI(TAG, "clock set, starting scan windows (%d ms scan, %d ms send)", SCAN_WINDOW_MS, SEND_WINDOW_MS);

    run_windows();
}
