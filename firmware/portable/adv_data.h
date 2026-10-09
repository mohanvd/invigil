// Reads the manufacturer company ID from BLE advertising data.
//
// Advertising data is a list of AD structures: one length byte, then that
// many bytes made of one AD type byte and the data. Manufacturer Specific
// Data (type 0xFF) starts with the 2-byte Bluetooth SIG company ID, least
// significant byte first. Nothing else from the payload is read or kept.

#ifndef INVIGIL_ADV_DATA_H
#define INVIGIL_ADV_DATA_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define AD_TYPE_MANUFACTURER_DATA 0xFF

// Finds the first Manufacturer Specific Data structure that holds a full
// company ID. Returns false when there is none, or when the data is
// malformed before one is found (a structure that runs past the end).
// A length byte of 0 ends the data early, as the Core Specification allows.
bool adv_find_company_id(const uint8_t *data, size_t len, uint16_t *company_id);

// Formats a company ID the way the MQTT contract wants it: "0x004C".
// out must hold 7 bytes.
void adv_format_company_id(uint16_t company_id, char out[7]);

#endif
