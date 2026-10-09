#include "wifi_sta.h"

#include <inttypes.h>
#include <stdio.h>

#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"

#include "lwip/apps/sntp.h"
#include "lwip/ip4_addr.h"
#include "lwip/netif.h"

#include "config.h"
#include "payload.h"

typedef enum { WIFI_IDLE, WIFI_CONNECTING, WIFI_UP, WIFI_BACKOFF } wifi_state_t;

static wifi_state_t state = WIFI_IDLE;
static absolute_time_t attempt_started;
static absolute_time_t retry_at;
static uint32_t backoff_ms = RECONNECT_BACKOFF_MIN_MS;
static bool sntp_started;
static uint32_t syncs_reported;

// Clock, written by the SNTP callback in the lwIP context. Read with the
// async context lock held (cyw43_arch_lwip_begin), or from a callback.
static bool time_synced;
static int64_t epoch_offset_us;  // ms since epoch = (time_us_64() + epoch_offset_us) / 1000
static int64_t last_step_us;
static uint32_t sync_count;

// Frame counter on the station interface's output.
static netif_linkoutput_fn radio_linkoutput;
static volatile uint32_t tx_frames;

static err_t counting_linkoutput(struct netif *netif, struct pbuf *p) {
    tx_frames++;
    return radio_linkoutput(netif, p);
}

static void hook_linkoutput(void) {
    cyw43_arch_lwip_begin();
    struct netif *n = &cyw43_state.netif[CYW43_ITF_STA];
    if (n->linkoutput != NULL && n->linkoutput != counting_linkoutput) {
        radio_linkoutput = n->linkoutput;
        n->linkoutput = counting_linkoutput;
    }
    cyw43_arch_lwip_end();
}

static const char *link_status_name(int status) {
    switch (status) {
    case CYW43_LINK_DOWN: return "link down";
    case CYW43_LINK_JOIN: return "joined, no IP yet";
    case CYW43_LINK_NOIP: return "joined, no IP";
    case CYW43_LINK_UP: return "up";
    case CYW43_LINK_FAIL: return "connection failed";
    case CYW43_LINK_NONET: return "network not found";
    case CYW43_LINK_BADAUTH: return "wrong password";
    default: return "unknown";
    }
}

static int link_status(void) {
    cyw43_arch_lwip_begin();
    int status = cyw43_tcpip_link_status(&cyw43_state, CYW43_ITF_STA);
    cyw43_arch_lwip_end();
    return status;
}

// The channel the radio is on. The firmware's WLC_GET_CHANNEL answer starts
// with the hardware channel as a 32-bit number. Check the printed value
// against the router's settings on the real unit.
static int wifi_channel(void) {
    uint32_t info[3] = {0, 0, 0};  // hw_channel, target_channel, scan_channel
    if (cyw43_ioctl(&cyw43_state, CYW43_IOCTL_GET_CHANNEL, sizeof(info), (uint8_t *)info, CYW43_ITF_STA) != 0) {
        return -1;
    }
    return (int)info[0];
}

static void print_link_details(void) {
    cyw43_arch_lwip_begin();
    const char *ip = ip4addr_ntoa(netif_ip4_addr(&cyw43_state.netif[CYW43_ITF_STA]));
    printf("wifi: connected to \"%s\", IP %s\n", WIFI_SSID, ip);
    cyw43_arch_lwip_end();

    int32_t rssi = 0;
    int rssi_err = cyw43_wifi_get_rssi(&cyw43_state, &rssi);
    int ch = wifi_channel();
    if (ch >= 1 && ch <= 14) {
        // 20 MHz around the centre frequency, as nRF channels (MHz - 2400).
        int mhz = ch == 14 ? 2484 : 2407 + 5 * ch;
        int lo = mhz - 10 - 2400;
        int hi = mhz + 10 - 2400;
        printf("wifi: channel %d (%d MHz, nRF channels %d-%d), RSSI %s%" PRId32 " dBm\n", ch, mhz,
               lo < 0 ? 0 : lo, hi > 125 ? 125 : hi, rssi_err ? "unknown " : "", rssi);
    } else {
        printf("wifi: channel unknown (%d), RSSI %s%" PRId32 " dBm\n", ch, rssi_err ? "unknown " : "", rssi);
    }
}

static void schedule_retry(void) {
    printf("wifi: retrying in %" PRIu32 " s\n", backoff_ms / 1000);
    retry_at = make_timeout_time_ms(backoff_ms);
    backoff_ms *= 2;
    if (backoff_ms > RECONNECT_BACKOFF_MAX_MS) {
        backoff_ms = RECONNECT_BACKOFF_MAX_MS;
    }
    state = WIFI_BACKOFF;
}

static void start_attempt(void) {
    printf("wifi: connecting to \"%s\"\n", WIFI_SSID);
    int err = cyw43_arch_wifi_connect_async(WIFI_SSID, WIFI_PASSWORD, CYW43_AUTH_WPA2_AES_PSK);
    if (err != 0) {
        printf("wifi: could not start connecting (error %d)\n", err);
        schedule_retry();
        return;
    }
    attempt_started = get_absolute_time();
    state = WIFI_CONNECTING;
}

static void start_sntp(void) {
    cyw43_arch_lwip_begin();
    sntp_setoperatingmode(SNTP_OPMODE_POLL);
    sntp_setservername(0, SNTP_SERVER);
    sntp_init();
    cyw43_arch_lwip_end();
    sntp_started = true;
    printf("sntp: asking %s for the time\n", SNTP_SERVER);
}

static void on_connected(void) {
    state = WIFI_UP;
    backoff_ms = RECONNECT_BACKOFF_MIN_MS;
    cyw43_wifi_pm(&cyw43_state, WIFI_PM_MODE);
    hook_linkoutput();
    print_link_details();
    if (!sntp_started) {
        start_sntp();
    }
}

// Prints a time in seconds since 1970 as a UTC date, so the clock can be
// checked by eye. Days to date conversion from Howard Hinnant's
// civil_from_days algorithm.
static void print_utc(int64_t secs) {
    int64_t days = secs / 86400;
    int64_t rem = secs % 86400;
    days += 719468;
    int64_t era = days / 146097;
    int64_t doe = days - era * 146097;
    int64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    int64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    int64_t mp = (5 * doy + 2) / 153;
    int day = (int)(doy - (153 * mp + 2) / 5 + 1);
    int month = (int)(mp < 10 ? mp + 3 : mp - 9);
    int year = (int)(yoe + era * 400 + (month <= 2));
    printf("sntp: clock set to %04d-%02d-%02d %02d:%02d:%02d UTC\n", year, month, day, (int)(rem / 3600),
           (int)(rem % 3600 / 60), (int)(rem % 60));
}

static void report_clock(void) {
    cyw43_arch_lwip_begin();
    uint32_t count = sync_count;
    int64_t offset = epoch_offset_us;
    int64_t step = last_step_us;
    cyw43_arch_lwip_end();
    if (count == syncs_reported) {
        return;
    }

    if (syncs_reported == 0) {
        print_utc((((int64_t)time_us_64() + offset) / 1000000));
        // The first answer cannot be corrected for network delay, because
        // lwIP skips the correction when the clock jumps by decades (it
        // started at 1970). Ask again now that the clock is close.
        cyw43_arch_lwip_begin();
        sntp_stop();
        sntp_init();
        cyw43_arch_lwip_end();
    } else {
        printf("sntp: clock corrected by %+" PRId64 " ms\n", step / 1000);
    }
    syncs_reported = count;
}

void wifi_sta_init(void) {
    cyw43_arch_enable_sta_mode();
    cyw43_wifi_pm(&cyw43_state, WIFI_PM_MODE);
    hook_linkoutput();
}

void wifi_sta_poll(void) {
    switch (state) {
    case WIFI_IDLE:
        start_attempt();
        break;
    case WIFI_BACKOFF:
        if (time_reached(retry_at)) {
            start_attempt();
        }
        break;
    case WIFI_CONNECTING: {
        int status = link_status();
        int64_t waited_ms = absolute_time_diff_us(attempt_started, get_absolute_time()) / 1000;
        if (status == CYW43_LINK_UP) {
            on_connected();
        } else if (status < 0 || waited_ms > WIFI_CONNECT_TIMEOUT_MS) {
            printf("wifi: %s\n", status < 0 ? link_status_name(status) : "timed out");
            cyw43_wifi_leave(&cyw43_state, CYW43_ITF_STA);
            schedule_retry();
        }
        break;
    }
    case WIFI_UP: {
        int status = link_status();
        if (status != CYW43_LINK_UP) {
            printf("wifi: lost (%s)\n", link_status_name(status));
            cyw43_wifi_leave(&cyw43_state, CYW43_ITF_STA);
            schedule_retry();
        }
        break;
    }
    }
    report_clock();
}

bool wifi_sta_up(void) {
    return state == WIFI_UP;
}

const char *wifi_sta_state_name(void) {
    switch (state) {
    case WIFI_IDLE: return "idle";
    case WIFI_CONNECTING: return "connecting";
    case WIFI_UP: return "up";
    case WIFI_BACKOFF: return "backoff";
    }
    return "unknown";
}

bool wifi_sta_time_synced(void) {
    cyw43_arch_lwip_begin();
    bool synced = time_synced;
    cyw43_arch_lwip_end();
    return synced;
}

uint64_t wifi_sta_time_ms(void) {
    cyw43_arch_lwip_begin();
    int64_t offset = epoch_offset_us;
    cyw43_arch_lwip_end();
    return (uint64_t)(((int64_t)time_us_64() + offset) / 1000);
}

int wifi_sta_rssi(void) {
    int32_t rssi = 0;
    if (cyw43_wifi_get_rssi(&cyw43_state, &rssi) != 0) {
        return CONTRACT_MIN_RSSI;
    }
    if (rssi < CONTRACT_MIN_RSSI) {
        return CONTRACT_MIN_RSSI;
    }
    if (rssi > CONTRACT_MAX_RSSI) {
        return CONTRACT_MAX_RSSI;
    }
    return (int)rssi;
}

uint32_t wifi_sta_tx_frames(void) {
    return tx_frames;
}

// SNTP hooks (see lwipopts.h). lwIP calls them in its own context, with the
// async context lock already held.

void wifi_sta_sntp_set_time(uint32_t sec, uint32_t us) {
    int64_t offset = (int64_t)sec * 1000000 + us - (int64_t)time_us_64();
    if (time_synced) {
        last_step_us = offset - epoch_offset_us;
    }
    epoch_offset_us = offset;
    time_synced = true;
    sync_count++;
}

void wifi_sta_sntp_get_time(uint32_t *sec, uint32_t *us) {
    // Before the first sync this is time since boot, counted from 1970.
    uint64_t now = (uint64_t)((int64_t)time_us_64() + (time_synced ? epoch_offset_us : 0));
    *sec = (uint32_t)(now / 1000000);
    *us = (uint32_t)(now % 1000000);
}
