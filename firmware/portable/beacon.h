// Broker beacon: how the unit finds the laptop (docs/firmware.md, Finding
// the broker). Plain C with no Pico SDK includes, so the host tests cover it.
//
// The launcher broadcasts one UDP datagram a second to port BEACON_UDP_PORT:
//   invigil broker <mqtt port> <tag>
// tag is the first 16 hex chars of HMAC-SHA256 with the hash salt as the key
// and "invigil broker <mqtt port> <sender IPv4>" as the message. The unit
// checks the tag against the address the datagram came from, so a beacon
// copied by another device on the network cannot point the unit anywhere
// but the laptop that made it.
// invigil/beacon.py is the reference implementation.

#ifndef INVIGIL_BEACON_H
#define INVIGIL_BEACON_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define BEACON_UDP_PORT 18830
#define BEACON_PERIOD_MS 1000
#define BEACON_TAG_LEN 16
// "invigil broker 65535 " + tag + an optional line end.
#define BEACON_MAX_LEN 40
// A sender not heard for this long (3 missed beacons) is gone: its address
// is no longer used for a new connection, and another sender may replace it.
#define BEACON_LOST_MS 3500

typedef struct {
    uint8_t ip[4];  // a.b.c.d
    uint16_t port;  // MQTT port
} beacon_addr_t;

void hmac_sha256(const void *key, size_t key_len, const void *msg, size_t msg_len, uint8_t out[32]);

// out receives BEACON_TAG_LEN lowercase hex chars and a terminating NUL.
void beacon_tag(const char *key, uint16_t port, const uint8_t ip[4], char out[BEACON_TAG_LEN + 1]);

// True if data is a beacon signed with key by the sender at ip. Sets *port.
// An empty key never verifies.
bool beacon_verify(const char *key, const uint8_t *data, size_t len, const uint8_t ip[4], uint16_t *port);

// Which sender the unit follows. It keeps the first one it hears for as long
// as that one keeps sending, so two laptops on one network do not make the
// unit jump between them.
typedef struct {
    bool have;
    beacon_addr_t addr;
    uint32_t seen_ms;
} beacon_pick_t;

void beacon_pick_init(beacon_pick_t *p);
// A verified beacon arrived from this sender. now_ms may wrap around.
void beacon_pick_heard(beacon_pick_t *p, const beacon_addr_t *from, uint32_t now_ms);
// The followed sender, if it was heard within BEACON_LOST_MS.
bool beacon_pick_live(const beacon_pick_t *p, uint32_t now_ms, beacon_addr_t *out);
// The followed sender, however long ago it was heard.
bool beacon_pick_last(const beacon_pick_t *p, beacon_addr_t *out);

bool beacon_addr_equal(const beacon_addr_t *a, const beacon_addr_t *b);

#endif
