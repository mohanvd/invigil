#include "mqtt_link.h"

#include <stdio.h>

#include "config.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "mqtt_client.h"  // ESP-IDF MQTT library
#include "wifi_sta.h"

static const char *TAG = "mqtt";

static esp_mqtt_client_handle_t s_client;
static volatile bool s_connected;
static int64_t s_last_status_us = -1;

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    const esp_mqtt_event_handle_t e = data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        s_connected = true;
        ESP_LOGI(TAG, "connected to %s", g_config.mqtt_uri);
        break;
    case MQTT_EVENT_DISCONNECTED:
        if (s_connected) {
            ESP_LOGW(TAG, "disconnected from broker, reconnecting");
        }
        s_connected = false;
        break;
    case MQTT_EVENT_ERROR:
        if (e->error_handle->error_type == MQTT_ERROR_TYPE_CONNECTION_REFUSED) {
            ESP_LOGE(TAG, "broker refused the connection (code %d), check the username and password in secrets.h",
                     e->error_handle->connect_return_code);
        } else {
            ESP_LOGW(TAG, "cannot reach broker at %s, retrying", g_config.mqtt_uri);
        }
        break;
    default:
        break;
    }
}

void mqtt_link_start(void)
{
    static char client_id[16];
    snprintf(client_id, sizeof(client_id), "invigil-%s", g_config.node_id);

    const esp_mqtt_client_config_t cfg = {
        .broker.address.uri = g_config.mqtt_uri,
        .credentials.client_id = client_id,
        .credentials.username = g_config.mqtt_username[0] ? g_config.mqtt_username : NULL,
        .credentials.authentication.password = g_config.mqtt_password[0] ? g_config.mqtt_password : NULL,
        .session.keepalive = 30,
        .network.reconnect_timeout_ms = 3000,
    };
    s_client = esp_mqtt_client_init(&cfg);
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, on_event, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_client));
}

bool mqtt_link_connected(void)
{
    return s_connected;
}

bool mqtt_link_publish(const char *kind, const char *json)
{
    if (!s_connected) {
        return false;
    }
    char topic[40];
    snprintf(topic, sizeof(topic), "invigil/node/%s/%s", g_config.node_id, kind);
    return esp_mqtt_client_publish(s_client, topic, json, 0, 0, 0) >= 0;
}

void mqtt_link_status_if_due(void)
{
    const int64_t now_us = esp_timer_get_time();
    if (s_last_status_us >= 0 && now_us - s_last_status_us < STATUS_INTERVAL_MS * 1000LL) {
        return;
    }
    char json[160];
    snprintf(json, sizeof(json),
             "{\"ts\":%lld,\"node\":\"%s\",\"uptime_s\":%lld,\"wifi_rssi\":%d,\"fw\":\"%s\"}",
             (long long)now_ms(), g_config.node_id, (long long)(now_us / 1000000),
             wifi_sta_rssi(), esp_app_get_description()->version);
    if (mqtt_link_publish("status", json)) {
        s_last_status_us = now_us;
    }
}
