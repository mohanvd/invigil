// Invigil sensor unit firmware: Raspberry Pi Pico 2 W + nRF24L01+PA+LNA.
//
// The unit repeats one cycle (docs/contract.md):
//   1. Scan window: BLE scan on, nRF sweeps back to back, no MQTT traffic.
//   2. Send window: BLE scan off, sweeps stopped. Publish the window's
//      spectrum message, then buffered BLE readings, then status if due.
//   3. Quiet gap, then the next scan window.
// The cycle only runs while Wi-Fi is up, the clock is set and MQTT is
// connected. Reconnecting happens between cycles, never inside a scan window.

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "hardware/watchdog.h"
#include "pico/cyw43_arch.h"
#include "pico/stdio_usb.h"
#include "pico/stdlib.h"

#include "ble_scan.h"
#include "config.h"
#include "mqtt_link.h"
#include "nrf_scan.h"
#include "payload.h"
#include "wifi_sta.h"

typedef enum { LED_SLOW, LED_FAST, LED_SOLID, LED_FAULT } led_mode_t;

// Results of the boot self-checks.
static bool hash_ok;
static bool nrf_ok;
static bool node_ok;

static char topic_ble[TOPIC_MAX_LEN];
static char topic_spectrum[TOPIC_MAX_LEN];
static char topic_status[TOPIC_MAX_LEN];
static char payload[PAYLOAD_SPECTRUM_MAX_LEN];

static bool led_on;
static absolute_time_t next_status;
static absolute_time_t next_summary;

// Counts since the last summary line.
static struct {
    uint32_t windows;
    uint32_t sweeps;            // sweeps counted in spectrum messages
    uint32_t sweeps_discarded;  // sweeps dropped because lwIP sent a frame during them
    uint64_t sweep_us_total;
    uint32_t sweep_us_max;
    uint32_t sweeps_timed;
    uint32_t tx_in_scan;        // frames lwIP handed to the radio during scan windows
    uint32_t ble_published;
    uint32_t ble_invalid;       // readings that failed the contract check, dropped
    uint32_t spectrum_sent;
    uint32_t spectrum_dropped;
    uint32_t status_sent;
    uint32_t mqtt_busy;         // ERR_MEM waits for the output buffer to drain
    uint32_t send_overruns;     // send windows that hit SEND_WINDOW_MAX_MS before draining
    uint32_t send_ms_max;
} stats;

static void led_poll(void) {
    led_mode_t mode;
    if (!hash_ok || !nrf_ok || !node_ok) {
        mode = LED_FAULT;
    } else if (!wifi_sta_up()) {
        mode = LED_SLOW;
    } else if (!wifi_sta_time_synced() || !mqtt_link_connected()) {
        mode = LED_FAST;
    } else {
        mode = LED_SOLID;
    }

    uint32_t t = to_ms_since_boot(get_absolute_time());
    bool on = true;
    switch (mode) {
    case LED_SLOW:  // connecting to Wi-Fi
        on = (t / 500) % 2 == 0;
        break;
    case LED_FAST:  // waiting for the clock or the broker
        on = (t / 100) % 2 == 0;
        break;
    case LED_SOLID:  // running
        on = true;
        break;
    case LED_FAULT: {  // a self-check failed: 3 short blinks, then a pause
        uint32_t p = t % 1500;
        on = p < 900 && p % 300 < 150;
        break;
    }
    }
    if (on != led_on) {
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
        led_on = on;
    }
}

// Things that must keep happening inside the scan and send windows.
// Nothing here transmits.
static void tick(void) {
    watchdog_update();
    led_poll();
}

static void wait_ms(uint32_t ms) {
    absolute_time_t until = make_timeout_time_ms(ms);
    while (!time_reached(until)) {
        tick();
        sleep_ms(1);
    }
}

static bool running(void) {
    return node_ok && wifi_sta_up() && wifi_sta_time_synced() && mqtt_link_connected();
}

// Publishes one message, waiting for the output buffer to drain if it is
// full, until the given time. Returns false if it could not be sent.
static bool publish_until(const char *topic, const char *msg, size_t len, absolute_time_t until) {
    for (;;) {
        mqtt_pub_result_t result = mqtt_link_publish(topic, msg, len);
        if (result == MQTT_PUB_OK) {
            return true;
        }
        if (result != MQTT_PUB_BUSY || time_reached(until)) {
            return false;
        }
        stats.mqtt_busy++;
        tick();
        sleep_us(500);
    }
}

// Returns the time the scan window ended, in ms since the epoch.
static uint64_t scan_window(void) {
    absolute_time_t end = make_timeout_time_ms(SCAN_WINDOW_MS);
    uint32_t tx_start = wifi_sta_tx_frames();
    uint32_t last_sweep_us = 0;

    ble_scan_start();
    nrf_scan_begin_window();
    for (;;) {
        tick();
        if (!nrf_ok) {
            if (time_reached(end)) {
                break;
            }
            sleep_ms(1);
            continue;
        }
        // Only start a sweep that can finish inside the window.
        if (absolute_time_diff_us(get_absolute_time(), end) < (int64_t)last_sweep_us) {
            break;
        }
        uint32_t tx_before = wifi_sta_tx_frames();
        last_sweep_us = nrf_scan_sweep();
        if (wifi_sta_tx_frames() == tx_before) {
            nrf_scan_keep_sweep();
        } else {
            stats.sweeps_discarded++;  // the unit itself transmitted during this sweep
        }
        stats.sweep_us_total += last_sweep_us;
        stats.sweeps_timed++;
        if (last_sweep_us > stats.sweep_us_max) {
            stats.sweep_us_max = last_sweep_us;
        }
    }
    ble_scan_stop();
    if (nrf_ok) {
        nrf_scan_end_window();
    }

    stats.windows++;
    stats.tx_in_scan += wifi_sta_tx_frames() - tx_start;
    return wifi_sta_time_ms();
}

static void send_window(uint64_t scan_end_ms) {
    absolute_time_t start = get_absolute_time();
    absolute_time_t stop_queueing = delayed_by_ms(start, SEND_WINDOW_MAX_MS - SEND_DRAIN_MS);
    absolute_time_t deadline = delayed_by_ms(start, SEND_WINDOW_MAX_MS);

    // 1. One spectrum message for the scan window. ts is the end of the window.
    const spectrum_t *spectrum = nrf_scan_window();
    if (nrf_ok && spectrum->sweeps > 0) {
        size_t n = payload_spectrum(payload, sizeof(payload), scan_end_ms, NODE_ID, spectrum);
        if (n > 0 && publish_until(topic_spectrum, payload, n, stop_queueing)) {
            stats.spectrum_sent++;
            stats.sweeps += spectrum->sweeps;
        } else {
            stats.spectrum_dropped++;
        }
    }

    // 2. Buffered BLE readings, oldest first. What does not fit waits for
    //    the next send window. Peek, publish and pop happen under one lock,
    //    so a reading leaves the buffer only once lwIP has taken it.
    while (!time_reached(stop_queueing)) {
        tick();
        ble_reading_t r;
        mqtt_pub_result_t result = MQTT_PUB_OK;
        cyw43_arch_lwip_begin();
        bool have = ble_scan_peek_locked(&r);
        if (have) {
            size_t n = payload_ble(payload, sizeof(payload), r.ts_ms, NODE_ID, r.addr, r.rssi, r.has_mfr, r.mfr);
            result = n > 0 ? mqtt_link_publish(topic_ble, payload, n) : MQTT_PUB_ERROR;
            if (result == MQTT_PUB_OK) {
                ble_scan_pop_locked();
                stats.ble_published++;
            } else if (result == MQTT_PUB_ERROR) {
                ble_scan_pop_locked();  // can never be sent; do not block the rest
                stats.ble_invalid++;
            }
        }
        cyw43_arch_lwip_end();
        if (!have || result == MQTT_PUB_DOWN) {
            break;
        }
        if (result == MQTT_PUB_BUSY) {
            stats.mqtt_busy++;  // output buffer full: let lwIP drain it, then retry
            sleep_us(500);
        }
    }

    // 3. Status, if due.
    if (time_reached(next_status) && !time_reached(stop_queueing)) {
        uint32_t uptime_s = (uint32_t)(time_us_64() / 1000000);
        size_t n = payload_status(payload, sizeof(payload), wifi_sta_time_ms(), NODE_ID, uptime_s,
                                  wifi_sta_rssi(), INVIGIL_FW_VERSION);
        if (n > 0 && publish_until(topic_status, payload, n, stop_queueing)) {
            stats.status_sent++;
            next_status = delayed_by_ms(next_status, STATUS_PERIOD_MS);
            if (time_reached(next_status)) {
                next_status = make_timeout_time_ms(STATUS_PERIOD_MS);  // was paused, do not catch up
            }
        }
    }

    // 4. Wait until everything handed to MQTT has left lwIP for the radio.
    while (!mqtt_link_drained() && !time_reached(deadline)) {
        tick();
        sleep_us(200);
    }
    if (!mqtt_link_drained()) {
        stats.send_overruns++;
    }

    uint32_t send_ms = (uint32_t)(absolute_time_diff_us(start, get_absolute_time()) / 1000);
    if (send_ms > stats.send_ms_max) {
        stats.send_ms_max = send_ms;
    }
}

static void run_cycle(void) {
    uint64_t scan_end_ms = scan_window();
    send_window(scan_end_ms);
    wait_ms(QUIET_GAP_MS);
}

static void print_summary(void) {
    ble_scan_counts_t ble = ble_scan_take_counts();
    uint32_t per_window = stats.spectrum_sent ? stats.sweeps / stats.spectrum_sent : 0;
    uint32_t sweep_us = stats.sweeps_timed ? (uint32_t)(stats.sweep_us_total / stats.sweeps_timed) : 0;

    printf("summary t=%" PRIu32 "s windows=%" PRIu32 " sweeps_per_window=%" PRIu32 " sweep_us=%" PRIu32
           " sweep_us_max=%" PRIu32 " ble_captured=%" PRIu32 " ble_published=%" PRIu32 " ble_dropped=%" PRIu32
           " ble_buffered=%" PRIu32 " spectrum_sent=%" PRIu32 " spectrum_dropped=%" PRIu32 " status_sent=%" PRIu32
           " send_ms_max=%" PRIu32 " mqtt_busy=%" PRIu32 " send_overruns=%" PRIu32 " tx_in_scan=%" PRIu32
           " sweeps_discarded=%" PRIu32 " wifi=%s mqtt=%s",
           (uint32_t)(time_us_64() / 1000000), stats.windows, per_window, sweep_us, stats.sweep_us_max,
           ble.captured, stats.ble_published, ble.dropped, ble.buffered, stats.spectrum_sent,
           stats.spectrum_dropped, stats.status_sent, stats.send_ms_max, stats.mqtt_busy, stats.send_overruns,
           stats.tx_in_scan, stats.sweeps_discarded, wifi_sta_state_name(), mqtt_link_state_name());
    if (ble.no_rssi || stats.ble_invalid) {
        printf(" ble_no_rssi=%" PRIu32 " ble_invalid=%" PRIu32, ble.no_rssi, stats.ble_invalid);
    }
    if (!hash_ok || !nrf_ok || !node_ok) {
        printf(" SELF-CHECK FAILED:%s%s%s", hash_ok ? "" : " hash", nrf_ok ? "" : " nrf", node_ok ? "" : " node");
    }
    printf("\n");
    memset(&stats, 0, sizeof(stats));
}

static void housekeeping(void) {
    watchdog_update();
    wifi_sta_poll();
    mqtt_link_poll(wifi_sta_up() && wifi_sta_time_synced());
    led_poll();
    if (time_reached(next_summary)) {
        next_summary = delayed_by_ms(next_summary, SUMMARY_PERIOD_MS);
        print_summary();
    }
}

static void wait_for_usb_terminal(void) {
    absolute_time_t until = make_timeout_time_ms(USB_WAIT_MS);
    while (!stdio_usb_connected() && !time_reached(until)) {
        sleep_ms(10);
    }
}

static bool build_topics(void) {
    return payload_topic(topic_ble, sizeof(topic_ble), NODE_ID, "ble") > 0 &&
           payload_topic(topic_spectrum, sizeof(topic_spectrum), NODE_ID, "spectrum") > 0 &&
           payload_topic(topic_status, sizeof(topic_status), NODE_ID, "status") > 0;
}

int main(void) {
    stdio_init_all();
    wait_for_usb_terminal();

    printf("\nInvigil unit %s, firmware %s, Pico SDK %s\n", NODE_ID, INVIGIL_FW_VERSION, PICO_SDK_VERSION_STRING);
    printf("last reset: %s\n", watchdog_enable_caused_reboot() ? "WATCHDOG TIMEOUT" : "not a watchdog timeout");

    // Wi-Fi country: Egypt.
    if (cyw43_arch_init_with_country(CYW43_COUNTRY('E', 'G', 0)) != 0) {
        printf("FAIL: the CYW43 radio chip did not start. Rebooting in 5 s.\n");
        sleep_ms(5000);
        watchdog_reboot(0, 0, 0);
        for (;;) {
            tight_loop_contents();
        }
    }
    watchdog_enable(WATCHDOG_TIMEOUT_MS, true);

    printf("self-checks:\n");
    node_ok = build_topics();
    printf("  %s  node ID \"%s\"\n", node_ok ? "PASS" : "FAIL", NODE_ID);
    hash_ok = ble_scan_init();
    nrf_ok = nrf_scan_init();
    printf("timing: scan %d ms, send up to %d ms, quiet gap %d ms, status every %d ms\n", SCAN_WINDOW_MS,
           SEND_WINDOW_MAX_MS, QUIET_GAP_MS, STATUS_PERIOD_MS);

    wifi_sta_init();
    mqtt_link_init();
    next_status = get_absolute_time();
    next_summary = make_timeout_time_ms(SUMMARY_PERIOD_MS);

    for (;;) {
        housekeeping();
        if (running()) {
            run_cycle();
        } else {
            sleep_ms(10);
        }
    }
}
