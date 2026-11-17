#include "mqtt_link.h"

#include <inttypes.h>
#include <stdio.h>

#include "beacon.h"
#include "broker_find.h"
#include "config.h"

// lwIP's mqtt.h defines its own MQTT_PORT (the standard 1883). Keep the port
// from secrets.h under another name so lwIP's cannot replace it.
enum { FALLBACK_PORT = MQTT_PORT };
#undef MQTT_PORT

#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"

#include "lwip/apps/mqtt.h"
#include "lwip/apps/mqtt_priv.h"  // the client struct, to allocate it statically and read its queue
#include "lwip/ip_addr.h"
#include "lwip/tcp.h"

#if LWIP_ALTCP
#error "mqtt_link reads the TCP send queue directly and needs LWIP_ALTCP 0"
#endif

// How the lwIP MQTT client behaves here (lwIP src/apps/mqtt/mqtt.c):
// - Keep alive: the cyclic timer only appends a PINGREQ to the output buffer
//   after MQTT_KEEPALIVE_S with nothing acknowledged. It does not send it;
//   the next publish or TCP ack does. Every send window publishes, so the
//   PINGREQ never goes out on its own during a scan window.
// - A QoS 0 publish holds a request slot until TCP acknowledges it, and
//   mqtt_publish() returns ERR_MEM when the slots or the output buffer run
//   out. The caller waits for them to drain and retries.

// Which broker (docs/firmware.md, Finding the broker):
// 1. The laptop whose beacon is being heard (broker_find).
// 2. After BROKER_BEACON_WAIT_MS without one: MQTT_HOST from secrets.h if it
//    is set, else the last laptop a beacon was heard from.
// While connected, a beacon from another address means the broker has moved:
// the old connection is dropped and a new one made, between cycles.

typedef enum { LINK_IDLE, LINK_CONNECTING, LINK_CONNECTED, LINK_BACKOFF } link_state_t;

static mqtt_client_t client;  // zeroed, which is the disconnected state
static struct mqtt_connect_client_info_t client_info;
static char client_id[32];
static ip_addr_t broker;  // the broker in use, or being tried
static uint16_t broker_port;
static const char *broker_source = "";
static ip_addr_t fallback;  // MQTT_HOST
static bool have_fallback;
static link_state_t state = LINK_IDLE;
// Listening for a beacon before a connection attempt.
static bool searching;
static absolute_time_t search_started;
static bool search_reported;
static absolute_time_t next_bad_beacon_report;
static absolute_time_t attempt_started;
static absolute_time_t retry_at;
static uint32_t backoff_ms = RECONNECT_BACKOFF_MIN_MS;

// Set by the connection callback (lwIP context), read with the lock held.
static bool status_pending;
static mqtt_connection_status_t pending_status;

static const char *status_name(mqtt_connection_status_t status) {
    switch (status) {
    case MQTT_CONNECT_ACCEPTED: return "accepted";
    case MQTT_CONNECT_REFUSED_PROTOCOL_VERSION: return "refused: protocol version";
    case MQTT_CONNECT_REFUSED_IDENTIFIER: return "refused: client id";
    case MQTT_CONNECT_REFUSED_SERVER: return "refused: server unavailable";
    case MQTT_CONNECT_REFUSED_USERNAME_PASS: return "refused: bad user name or password";
    case MQTT_CONNECT_REFUSED_NOT_AUTHORIZED_: return "refused: not authorized";
    case MQTT_CONNECT_DISCONNECTED: return "disconnected";
    case MQTT_CONNECT_TIMEOUT: return "timed out";
    }
    return "unknown";
}

static void on_connection(mqtt_client_t *c, void *arg, mqtt_connection_status_t status) {
    (void)arg;
    if (status == MQTT_CONNECT_ACCEPTED && c->conn != NULL) {
        // Send each publish at once. With Nagle on, small messages wait for
        // the broker's delayed ack (up to 200 ms on Windows), which would not
        // fit in a send window.
        tcp_nagle_disable(c->conn);
    }
    pending_status = status;
    status_pending = true;
}

static void schedule_retry(void) {
    printf("mqtt: retrying in %" PRIu32 " s\n", backoff_ms / 1000);
    retry_at = make_timeout_time_ms(backoff_ms);
    backoff_ms *= 2;
    if (backoff_ms > RECONNECT_BACKOFF_MAX_MS) {
        backoff_ms = RECONNECT_BACKOFF_MAX_MS;
    }
    state = LINK_BACKOFF;
}

// Chooses the broker for the next attempt. Returns false to keep listening.
static bool pick_broker(void) {
    if (broker_find_live(&broker, &broker_port)) {
        broker_source = "beacon";
        return true;
    }
    if (absolute_time_diff_us(search_started, get_absolute_time()) < BROKER_BEACON_WAIT_MS * 1000LL) {
        return false;
    }
    if (have_fallback) {
        broker = fallback;
        broker_port = FALLBACK_PORT;
        broker_source = "MQTT_HOST in secrets.h, no beacon heard";
        return true;
    }
    if (broker_find_last(&broker, &broker_port)) {
        broker_source = "last beacon heard";
        return true;
    }
    if (!search_reported) {
        search_reported = true;
        printf("mqtt: no broker beacon on UDP port %d yet. Is the launcher running (invigil start) on this "
               "network? Still listening.\n",
               BEACON_UDP_PORT);
    }
    return false;
}

// A beacon with a wrong signature is most likely a laptop with another salt.
static void report_bad_beacons(void) {
    if (!time_reached(next_bad_beacon_report)) {
        return;
    }
    broker_find_counts_t counts = broker_find_take_counts();
    if (counts.heard == 0 && counts.rejected > 0) {
        printf("mqtt: ignored %" PRIu32 " beacons with a wrong signature. HASH_SALT in secrets.h must be the "
               "same as hash_salt in server/config.toml\n",
               counts.rejected);
    }
    next_bad_beacon_report = make_timeout_time_ms(BROKER_BEACON_WAIT_MS);
}

static void start_connect(void) {
    printf("mqtt: connecting to %s:%u (%s) as %s\n", ipaddr_ntoa(&broker), (unsigned)broker_port, broker_source,
           client_id);
    cyw43_arch_lwip_begin();
    status_pending = false;
    err_t err = mqtt_client_connect(&client, &broker, broker_port, on_connection, NULL, &client_info);
    cyw43_arch_lwip_end();
    if (err != ERR_OK) {
        printf("mqtt: could not start connecting (lwIP error %d)\n", err);
        schedule_retry();
        return;
    }
    attempt_started = get_absolute_time();
    state = LINK_CONNECTING;
}

void mqtt_link_init(void) {
    snprintf(client_id, sizeof(client_id), "invigil-%s", NODE_ID);
    client_info.client_id = client_id;
    // MQTT allows a user name without a password, not the other way round.
    client_info.client_user = MQTT_USER[0] ? MQTT_USER : NULL;
    client_info.client_pass = (MQTT_USER[0] && MQTT_PASSWORD[0]) ? MQTT_PASSWORD : NULL;
    client_info.keep_alive = MQTT_KEEPALIVE_S;
    client_info.will_topic = NULL;

    if (MQTT_HOST[0] != '\0') {
        have_fallback = ipaddr_aton(MQTT_HOST, &fallback) != 0;
        if (!have_fallback) {
            printf("mqtt: MQTT_HOST \"%s\" is not an IPv4 address, so there is no fallback. Fix "
                   "firmware/secrets.h or leave it empty\n",
                   MQTT_HOST);
        }
    }
    printf("mqtt: the broker is found by its beacon on UDP port %d", BEACON_UDP_PORT);
    if (have_fallback) {
        printf(", fallback %s:%d", MQTT_HOST, FALLBACK_PORT);
    }
    printf("\n");
}

// The beacon now comes from another address: the laptop got a new IP, or
// another laptop took over. Drops the connection with a TCP reset, which is
// one frame at most. A normal close would keep resending to an address that
// may be gone, into the scan windows that follow.
static void move_if_broker_moved(void) {
    ip_addr_t heard;
    uint16_t heard_port;
    if (!broker_find_live(&heard, &heard_port) || (ip_addr_cmp(&heard, &broker) && heard_port == broker_port)) {
        return;
    }
    // ipaddr_ntoa has one buffer, so one address per printf.
    printf("mqtt: the broker beacon now comes from %s:%u", ipaddr_ntoa(&heard), (unsigned)heard_port);
    printf(", leaving %s:%u\n", ipaddr_ntoa(&broker), (unsigned)broker_port);
    cyw43_arch_lwip_begin();
    if (client.conn != NULL) {
        tcp_abort(client.conn);  // lwIP's error callback then closes the MQTT client
    } else {
        mqtt_disconnect(&client);
    }
    status_pending = false;
    cyw43_arch_lwip_end();
    backoff_ms = RECONNECT_BACKOFF_MIN_MS;
    state = LINK_IDLE;
}

void mqtt_link_poll(bool network_ready) {
    cyw43_arch_lwip_begin();
    bool changed = status_pending;
    mqtt_connection_status_t status = pending_status;
    status_pending = false;
    bool connected = mqtt_client_is_connected(&client);
    cyw43_arch_lwip_end();

    if (changed) {
        if (status == MQTT_CONNECT_ACCEPTED) {
            printf("mqtt: connected\n");
            backoff_ms = RECONNECT_BACKOFF_MIN_MS;
            state = LINK_CONNECTED;
        } else {
            printf("mqtt: %s\n", status_name(status));
            schedule_retry();
        }
    } else if (state == LINK_CONNECTED && !connected) {
        printf("mqtt: connection lost\n");
        schedule_retry();
    } else if (state == LINK_CONNECTING &&
               absolute_time_diff_us(attempt_started, get_absolute_time()) > MQTT_CONNECT_TIMEOUT_MS * 1000LL) {
        printf("mqtt: no answer from the broker\n");
        cyw43_arch_lwip_begin();
        mqtt_disconnect(&client);  // no callback after this
        status_pending = false;
        cyw43_arch_lwip_end();
        schedule_retry();
    }

    if (!network_ready) {
        searching = false;
        return;
    }
    if (state == LINK_CONNECTED || state == LINK_CONNECTING) {
        move_if_broker_moved();
    }
    if (state == LINK_IDLE || (state == LINK_BACKOFF && time_reached(retry_at))) {
        if (!searching) {
            searching = true;
            search_started = get_absolute_time();
            search_reported = false;
        }
        report_bad_beacons();
        if (pick_broker()) {
            searching = false;
            start_connect();
        }
    }
}

bool mqtt_link_connected(void) {
    cyw43_arch_lwip_begin();
    bool connected = state == LINK_CONNECTED && mqtt_client_is_connected(&client);
    cyw43_arch_lwip_end();
    return connected;
}

const char *mqtt_link_state_name(void) {
    if (searching) {
        return "finding-broker";
    }
    switch (state) {
    case LINK_IDLE: return "idle";
    case LINK_CONNECTING: return "connecting";
    case LINK_CONNECTED: return "connected";
    case LINK_BACKOFF: return "backoff";
    }
    return "unknown";
}

mqtt_pub_result_t mqtt_link_publish(const char *topic, const char *payload, size_t len) {
    if (len > 0xFFFF) {
        return MQTT_PUB_ERROR;
    }
    cyw43_arch_lwip_begin();
    err_t err = ERR_CONN;
    if (mqtt_client_is_connected(&client)) {
        err = mqtt_publish(&client, topic, payload, (u16_t)len, 0, 0, NULL, NULL);
    }
    cyw43_arch_lwip_end();

    switch (err) {
    case ERR_OK: return MQTT_PUB_OK;
    case ERR_MEM: return MQTT_PUB_BUSY;
    case ERR_CONN: return MQTT_PUB_DOWN;
    default: return MQTT_PUB_ERROR;
    }
}

bool mqtt_link_drained(void) {
    cyw43_arch_lwip_begin();
    bool drained = true;
    if (client.conn != NULL) {
        // unacked too: a segment still waiting for its ack can be sent again
        // by TCP at any moment, which could land in the next scan window.
        drained = client.output.put == client.output.get && client.conn->unsent == NULL &&
                  client.conn->unacked == NULL;
    }
    cyw43_arch_lwip_end();
    return drained;
}
