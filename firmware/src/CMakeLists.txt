idf_component_register(
    SRCS "main.c" "config.c" "wifi_sta.c" "mqtt_link.c" "ble_scan.c"
    INCLUDE_DIRS "."
    # espressif/mqtt comes from idf_component.yml and is added automatically.
    PRIV_REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_timer esp_app_format bt mbedtls
)
