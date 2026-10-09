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

#include "spectrum.h"

// Limits from server/contract.py.
#define CONTRACT_MIN_TS_MS 1600000000000ULL  // below this the clock is not synced
#define CONTRACT_MAX_TS_MS 9999999999999ULL
#define CONTRACT_MIN_RSSI (-127)
#define CONTRACT_MAX_RSSI 0
#define CONTRACT_MAX_UPTIME_S 2147483647UL
#define CONTRACT_MAX_FW_LEN 32

// Buffer sizes that fit the largest valid message of each kind.
#define TOPIC_MAX_LEN 64
#define PAYLOAD_BLE_MAX_LEN 128
#define PAYLOAD_STATUS_MAX_LEN 160
#define PAYLOAD_SPECTRUM_MAX_LEN 1024  // 126 counts of up to 5 digits plus commas

// A node ID is 1 to 16 letters, digits, '-' or '_', so it is safe in a topic.
bool payload_node_is_valid(const char *node);

// "invigil/node/{node}/{kind}" with kind "ble", "spectrum" or "status".
size_t payload_topic(char *buf, size_t cap, const char *node, const char *kind);

// {"ts":...,"node":"N1","addr":"a91f03c2d4e8","rssi":-58,"mfr":"0x004C"}
// addr must be a 12-char lowercase hex hash. mfr is null when has_mfr is false.
size_t payload_ble(char *buf, size_t cap, uint64_t ts_ms, const char *node, const char *addr,
                   int rssi, bool has_mfr, uint16_t mfr);

// {"ts":...,"node":"N1","sweeps":50,"hits":[126 integers]}
size_t payload_spectrum(char *buf, size_t cap, uint64_t ts_ms, const char *node,
                        const spectrum_t *spectrum);

// {"ts":...,"node":"N1","uptime_s":3600,"wifi_rssi":-61,"fw":"0.1.0"}
size_t payload_status(char *buf, size_t cap, uint64_t ts_ms, const char *node, uint32_t uptime_s,
                      int wifi_rssi, const char *fw);

#endif
