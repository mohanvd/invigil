#include "adv_data.h"

bool adv_find_company_id(const uint8_t *data, size_t len, uint16_t *company_id) {
    size_t pos = 0;
    while (pos < len) {
        size_t field_len = data[pos];
        if (field_len == 0) {
            return false;  // end of the significant part
        }
        if (pos + 1 + field_len > len) {
            return false;  // runs past the end: malformed
        }
        uint8_t type = data[pos + 1];
        // field_len counts the type byte, so a company ID needs at least 3.
        if (type == AD_TYPE_MANUFACTURER_DATA && field_len >= 3) {
            *company_id = (uint16_t)(data[pos + 2] | (data[pos + 3] << 8));
            return true;
        }
        pos += 1 + field_len;
    }
    return false;
}

void adv_format_company_id(uint16_t company_id, char out[7]) {
    static const char hex[] = "0123456789ABCDEF";
    out[0] = '0';
    out[1] = 'x';
    out[2] = hex[(company_id >> 12) & 0xf];
    out[3] = hex[(company_id >> 8) & 0xf];
    out[4] = hex[(company_id >> 4) & 0xf];
    out[5] = hex[company_id & 0xf];
    out[6] = '\0';
}
