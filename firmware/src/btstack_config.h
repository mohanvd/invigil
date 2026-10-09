// BTstack configuration for the Invigil unit: BLE observer only.
//
// The unit only scans for advertisements, passively. It never advertises,
// never connects and never pairs. BTstack keeps LE scanning under
// ENABLE_LE_CENTRAL, so that flag is on, but no code here starts a
// connection, and the peripheral role is left out.
// Buffer sizes follow the Pico SDK BLE examples (pico-examples bluetooth/config).

#ifndef INVIGIL_BTSTACK_CONFIG_H
#define INVIGIL_BTSTACK_CONFIG_H

#define ENABLE_LE_CENTRAL
#define ENABLE_LOG_ERROR

// Buffers
#define HCI_OUTGOING_PRE_BUFFER_SIZE 4
#define HCI_ACL_PAYLOAD_SIZE (255 + 4)
#define HCI_ACL_CHUNK_SIZE_ALIGNMENT 4
#define MAX_NR_HCI_CONNECTIONS 1
#define MAX_NR_SM_LOOKUP_ENTRIES 3
#define MAX_NR_WHITELIST_ENTRIES 1
#define MAX_NR_LE_DEVICE_DB_ENTRIES 1

// Limit the controller buffers used by the stack to avoid overrunning the
// bus the CYW43 shares between Wi-Fi and Bluetooth.
#define MAX_NR_CONTROLLER_ACL_BUFFERS 3
#define MAX_NR_CONTROLLER_SCO_PACKETS 3
#define ENABLE_HCI_CONTROLLER_TO_HOST_FLOW_CONTROL
#define HCI_HOST_ACL_PACKET_LEN (255 + 4)
#define HCI_HOST_ACL_PACKET_NUM 3
#define HCI_HOST_SCO_PACKET_LEN 120
#define HCI_HOST_SCO_PACKET_NUM 3

// The Pico SDK sets up a key store in flash for BTstack. Nothing is ever
// paired, so it stays empty, but BTstack needs the sizes.
#define NVM_NUM_DEVICE_DB_ENTRIES 16
#define NVM_NUM_LINK_KEYS 16

// No malloc for BTstack.
#define MAX_ATT_DB_SIZE 512

#define HAVE_EMBEDDED_TIME_MS
#define HAVE_ASSERT
#define HCI_RESET_RESEND_TIMEOUT_MS 1000
#define ENABLE_SOFTWARE_AES128

#endif
