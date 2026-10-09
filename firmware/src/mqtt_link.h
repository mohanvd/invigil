// MQTT connection to Mosquitto on the laptop (lwIP MQTT app, QoS 0).

#ifndef INVIGIL_MQTT_LINK_H
#define INVIGIL_MQTT_LINK_H

#include <stdbool.h>
#include <stddef.h>

typedef enum {
    MQTT_PUB_OK,     // handed to lwIP
    MQTT_PUB_BUSY,   // output buffer full (ERR_MEM): wait for it to drain, then retry
    MQTT_PUB_DOWN,   // not connected
    MQTT_PUB_ERROR,  // refused for another reason; retrying will not help
} mqtt_pub_result_t;

void mqtt_link_init(void);

// Connects, and reconnects with backoff after a failure. Only connects while
// network_ready is true. Call from the main loop, never inside a scan window.
void mqtt_link_poll(bool network_ready);

bool mqtt_link_connected(void);
const char *mqtt_link_state_name(void);

// Publishes at QoS 0, not retained. Takes the async context lock itself; the
// lock is recursive, so it may also be called with the lock already held.
mqtt_pub_result_t mqtt_link_publish(const char *topic, const char *payload, size_t len);

// True when everything handed to mqtt_link_publish() has left lwIP for the
// radio: the MQTT output buffer is empty and TCP has no unsent segments.
// Acknowledgements may still be on their way back.
bool mqtt_link_drained(void);

#endif
