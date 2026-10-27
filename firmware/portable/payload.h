// MQTT topics and JSON payloads, exactly as docs/contract.md defines them.
//
// Every builder checks its inputs against the same ranges server/contract.py
// checks, and builds nothing (returns 0) if one is out of range or the buffer
// is too small. So the unit never publishes a message the logger would reject.
// The host tests write sample messages that CI runs through contract.py, so
// the two cannot drift apart.

#ifndef INVIGIL_PAYLOAD_H
#define INVIGIL_PAYLOAD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ble_ring.h"
#include "spectrum.h"

// Limits from server/contract.py.
#define CONTRACT_MIN_TS_MS 1600000000000ULL  // below this the clock is not synced
#define CONTRACT_MAX_TS_MS 9999999999999ULL
#define CONTRACT_MIN_RSSI (-127)
#define CONTRACT_MAX_RSSI 0
#define CONTRACT_MAX_UPTIME_S 2147483647UL
#define CONTRACT_MAX_FW_LEN 32

// The longest ble payload the unit sends, MAX_BLE_PAYLOAD_BYTES in
// server/contract.py. With the MQTT header and topic it fits one TCP segment
// (TCP_MSS 1460), and lwIP's MQTT output buffer holds several at once
// (docs/contract.md, Size limit).
#define CONTRACT_MAX_BLE_PAYLOAD 1400

// Buffer sizes that fit the largest valid message of each kind.
#define TOPIC_MAX_LEN 64
#define PAYLOAD_BLE_MAX_LEN (CONTRACT_MAX_BLE_PAYLOAD + 1)  // plus the NUL
#define PAYLOAD_STATUS_MAX_LEN 160
#define PAYLOAD_SPECTRUM_MAX_LEN 1024  // 126 counts of up to 5 digits plus commas

// A node ID is 1 to 16 letters, digits, '-' or '_', so it is safe in a topic.
bool payload_node_is_valid(const char *node);

// "invigil/node/{node}/{kind}" with kind "ble", "spectrum" or "status".
size_t payload_topic(char *buf, size_t cap, const char *node, const char *kind);

// One ble message, built one reading at a time:
// {"ts":...,"node":"N1","readings":[{"ts":...,"addr":"a91f03c2d4e8","rssi":-58,"mfr":"0x004C"},...]}
// ts is the end of the scan window. Each reading keeps its own ts. A reading's
// addr must be a 12-char lowercase hex hash, and mfr is null when has_mfr is
// false. The finished message is at most min(cap - 1, CONTRACT_MAX_BLE_PAYLOAD)
// bytes.
typedef struct {
    char *buf;
    size_t limit;    // longest message allowed, not counting the NUL
    size_t len;      // bytes written so far, without the closing "]}"
    uint32_t count;  // readings in the message
} ble_batch_t;

typedef enum {
    BLE_BATCH_ADDED,    // the reading is in the message
    BLE_BATCH_FULL,     // it does not fit: send this message, then start another
    BLE_BATCH_INVALID,  // off contract, or too big even for an empty message: never sendable
} ble_batch_result_t;

// Starts a message. False if ts or node is off contract or the buffer is too
// small for an empty message; the batch must not be used then.
bool ble_batch_begin(ble_batch_t *b, char *buf, size_t cap, uint64_t ts_ms, const char *node);
// Adds one reading. A reading that is FULL or INVALID leaves the message unchanged.
ble_batch_result_t ble_batch_add(ble_batch_t *b, const ble_reading_t *r);
// Closes the message and returns its length, or 0 (and an empty string) if
// it has no readings.
size_t ble_batch_finish(ble_batch_t *b);

// {"ts":...,"node":"N1","sweeps":50,"hits":[126 integers]}
size_t payload_spectrum(char *buf, size_t cap, uint64_t ts_ms, const char *node,
                        const spectrum_t *spectrum);

// {"ts":...,"node":"N1","uptime_s":3600,"wifi_rssi":-61,"fw":"0.1.0"}
size_t payload_status(char *buf, size_t cap, uint64_t ts_ms, const char *node, uint32_t uptime_s,
                      int wifi_rssi, const char *fw);

#endif
