// The mqtt_client module: broker connection, publishing, and the status message.
// Named mqtt_link because ESP-IDF's MQTT library already owns mqtt_client.h.

#pragma once

#include <stdbool.h>

// Connects to the broker from secrets.h. Reconnects on its own after any drop.
void mqtt_link_start(void);

bool mqtt_link_connected(void);

// Publishes JSON to invigil/node/{node_id}/{kind} at QoS 0.
// Returns false if the node is offline or the send failed.
// Call only during a send window.
bool mqtt_link_publish(const char *kind, const char *json);

// Publishes a status message if STATUS_INTERVAL_MS has passed since the last one.
// Call only during a send window.
void mqtt_link_status_if_due(void);
