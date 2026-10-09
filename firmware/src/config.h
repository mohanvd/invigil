// Settings for the Invigil unit: secrets, pins and timing.

#ifndef INVIGIL_CONFIG_H
#define INVIGIL_CONFIG_H

#if !__has_include("secrets.h")
#error "firmware/secrets.h is missing. Copy firmware/secrets.h.example to firmware/secrets.h and fill it in."
#endif
#include "secrets.h"

// Firmware version, from project(... VERSION ...) in firmware/CMakeLists.txt.
#ifndef INVIGIL_FW_VERSION
#error "INVIGIL_FW_VERSION is set by firmware/CMakeLists.txt"
#endif

// Set to 1 only for the one-time byte-order check in docs/firmware.md. It
// prints each raw Bluetooth address next to its hash on USB serial. Nothing
// raw is ever published or stored. Set it back to 0 before any real use.
#ifndef INVIGIL_DEBUG_RAW_ADDR
#define INVIGIL_DEBUG_RAW_ADDR 0
#endif

// ---------------------------------------------------------------------------
// Pins: nRF24L01+PA+LNA on SPI0. IRQ is not connected.
// ---------------------------------------------------------------------------
#define NRF_SPI spi0
#define NRF_PIN_MISO 16
#define NRF_PIN_CSN 17
#define NRF_PIN_SCK 18
#define NRF_PIN_MOSI 19
#define NRF_PIN_CE 20
// 4 MHz to start, because of jumper wires on a breadboard. The radio
// supports up to 10 MHz.
#define NRF_SPI_HZ 4000000

// ---------------------------------------------------------------------------
// Scan and send windows (docs/contract.md). Every value here is a starting
// guess. Measure each one on the real unit (docs/firmware.md, To measure).
// ---------------------------------------------------------------------------
// Scan window: BLE scan on, nRF sweeps back to back, no Wi-Fi traffic.
// Starting guess, to be measured.
#define SCAN_WINDOW_MS 1000
// Longest send window: publish the window's readings, then wait until
// everything has left lwIP. Starting guess, to be measured.
#define SEND_WINDOW_MAX_MS 300
// Part of the send window kept for the last messages to leave lwIP. No new
// message is handed to MQTT after SEND_WINDOW_MAX_MS - SEND_DRAIN_MS.
// Starting guess, to be measured.
#define SEND_DRAIN_MS 50
// Quiet time after the last publish has left lwIP, before the next scan
// window, so the radio has finished transmitting. Starting guess, to be measured.
#define QUIET_GAP_MS 50
// How often a status message is published. Starting guess, to be measured.
#define STATUS_PERIOD_MS 10000

// ---------------------------------------------------------------------------
// BLE scan (BTstack). Passive, duplicate filtering off.
// ---------------------------------------------------------------------------
// Scan interval and window in units of 0.625 ms. Equal values mean the
// controller listens all the time during a scan window. Starting guess, to
// be measured against how many advertisements are caught.
#define BLE_SCAN_INTERVAL 48  // 30 ms
#define BLE_SCAN_WINDOW 48    // 30 ms
// Readings buffered between send windows. When full, the oldest is dropped.
#define BLE_BUFFER_SIZE 1024

// ---------------------------------------------------------------------------
// Network
// ---------------------------------------------------------------------------
// Wi-Fi power saving. CYW43_NONE_PM keeps the radio awake, so it never sends
// the power-save frames the default mode sends about 200 ms after the last
// packet, which would land inside a scan window. Costs some battery.
// Compare with CYW43_PERFORMANCE_PM on the real unit (docs/firmware.md).
#define WIFI_PM_MODE CYW43_NONE_PM
// Give up on one connection attempt after this long and back off.
#define WIFI_CONNECT_TIMEOUT_MS 20000
// Give up on one MQTT connection attempt after this long and back off.
#define MQTT_CONNECT_TIMEOUT_MS 10000
// Reconnect backoff for Wi-Fi and MQTT: 1 s, doubling up to 30 s.
#define RECONNECT_BACKOFF_MIN_MS 1000
#define RECONNECT_BACKOFF_MAX_MS 30000
// MQTT keep alive in seconds. lwIP only queues a PINGREQ after this long
// with nothing sent, and every send window publishes, so in practice no
// PINGREQ is sent.
#define MQTT_KEEPALIVE_S 60

// ---------------------------------------------------------------------------
// Housekeeping
// ---------------------------------------------------------------------------
#define WATCHDOG_TIMEOUT_MS 8000
#define SUMMARY_PERIOD_MS 10000
// Wait this long at boot for a USB serial terminal, so the self-check
// results are not missed. The unit starts anyway when no terminal opens.
#define USB_WAIT_MS 3000

#endif
