#include "mqtt_link.h"

#include <inttypes.h>
#include <stdio.h>

#include "config.h"

// lwIP's mqtt.h defines its own MQTT_PORT (the standard 1883). Keep the port
// from secrets.h under another name so lwIP's cannot replace it.
enum { BROKER_PORT = MQTT_PORT };
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

typedef enum { LINK_IDLE, LINK_CONNECTING, LINK_CONNECTED, LINK_BACKOFF, LINK_BAD_CONFIG } link_state_t;

static mqtt_client_t client;  // zeroed, which is the disconnected state
static struct mqtt_connect_client_info_t client_info;
static char client_id[32];
static ip_addr_t broker;
static link_state_t state = LINK_IDLE;
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

static void start_connect(void) {
    printf("mqtt: connecting to %s:%d as %s\n", MQTT_HOST, BROKER_PORT, client_id);
    cyw43_arch_lwip_begin();
    status_pending = false;
    err_t err = mqtt_client_connect(&client, &broker, BROKER_PORT, on_connection, NULL, &client_info);
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

    if (!ipaddr_aton(MQTT_HOST, &broker)) {
        printf("mqtt: MQTT_HOST \"%s\" is not an IPv4 address. Fix firmware/secrets.h\n", MQTT_HOST);
        state = LINK_BAD_CONFIG;
    }
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
        return;
    }
    if (state == LINK_IDLE || (state == LINK_BACKOFF && time_reached(retry_at))) {
        start_connect();
    }
}

bool mqtt_link_connected(void) {
    cyw43_arch_lwip_begin();
    bool connected = state == LINK_CONNECTED && mqtt_client_is_connected(&client);
    cyw43_arch_lwip_end();
    return connected;
}

const char *mqtt_link_state_name(void) {
    switch (state) {
    case LINK_IDLE: return "idle";
    case LINK_CONNECTING: return "connecting";
    case LINK_CONNECTED: return "connected";
    case LINK_BACKOFF: return "backoff";
    case LINK_BAD_CONFIG: return "bad-host";
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
