// lwIP options for the Invigil unit.
// Based on pico-examples (pico_w/wifi/lwipopts_examples_common.h), sized for
// this traffic: one MQTT connection that publishes a burst once per send
// window, plus DHCP, DNS and SNTP.
// Option reference: https://www.nongnu.org/lwip/2_1_x/group__lwip__opts.html

#ifndef INVIGIL_LWIPOPTS_H
#define INVIGIL_LWIPOPTS_H

#include <stdint.h>

// Bare lwIP driven by the cyw43_arch threadsafe background context.
#define NO_SYS 1
#define LWIP_SOCKET 0
#define LWIP_NETCONN 0
// Must be 0 with the threadsafe background context (malloc from an IRQ).
#define MEM_LIBC_MALLOC 0
#define MEM_ALIGNMENT 4

// Heap for TCP data copied out of the MQTT output buffer (up to TCP_SND_BUF)
// and other dynamic pbufs. The RP2350 has plenty of RAM.
#define MEM_SIZE (32 * 1024)
#define MEMP_NUM_TCP_SEG 32
#define MEMP_NUM_ARP_QUEUE 10
#define PBUF_POOL_SIZE 24

#define LWIP_IPV4 1
#define LWIP_IPV6 0
#define LWIP_ARP 1
#define LWIP_ETHERNET 1
#define LWIP_ICMP 1
#define LWIP_RAW 1
#define LWIP_TCP 1
#define LWIP_UDP 1
#define LWIP_DNS 1
#define LWIP_DHCP 1
#define DHCP_DOES_ARP_CHECK 0
#define LWIP_DHCP_DOES_ACD_CHECK 0
// No TCP keepalive probes. MQTT has its own keep alive (see mqtt_link.c).
#define LWIP_TCP_KEEPALIVE 0
// The firmware reads the MQTT connection's TCP queue directly, which needs
// plain TCP without the altcp layer (no TLS).
#define LWIP_ALTCP 0

#define TCP_MSS 1460
#define TCP_WND (8 * TCP_MSS)
#define TCP_SND_BUF (8 * TCP_MSS)
#define TCP_SND_QUEUELEN ((4 * (TCP_SND_BUF) + (TCP_MSS - 1)) / (TCP_MSS))

#define LWIP_NETIF_STATUS_CALLBACK 1
#define LWIP_NETIF_LINK_CALLBACK 1
#define LWIP_NETIF_HOSTNAME 1
#define LWIP_NETIF_TX_SINGLE_PBUF 1
#define LWIP_CHKSUM_ALGORITHM 3

#define MEM_STATS 0
#define SYS_STATS 0
#define MEMP_STATS 0
#define LINK_STATS 0

// One timeout each for the MQTT cyclic timer and SNTP, on top of lwIP's own.
#define MEMP_NUM_SYS_TIMEOUT (LWIP_NUM_SYS_TIMEOUT_INTERNAL + 2)

// ---------------------------------------------------------------------------
// MQTT (lwIP MQTT app)
// ---------------------------------------------------------------------------
// lwIP's MQTT client only takes a publish when the whole packet fits in this
// buffer at once. The default (256 bytes) cannot hold one spectrum message
// (up to about 850 bytes with topic and header). 8 KB holds a spectrum
// message, five full ble messages (1400 bytes each, docs/contract.md) and a
// status message, so a send window rarely waits on it.
#define MQTT_OUTPUT_RINGBUF_SIZE 8192
// A QoS 0 publish holds a request slot until TCP acknowledges it. Enough
// slots that the output buffer, not the slots, is the limit.
#define MQTT_REQ_MAX_IN_FLIGHT 64

// ---------------------------------------------------------------------------
// SNTP (lwIP SNTP app)
// ---------------------------------------------------------------------------
#define SNTP_SERVER_DNS 1
#define SNTP_MAX_SERVERS 1
#define SNTP_GET_SERVERS_FROM_DHCP 0
// Check that a reply matches the request we sent.
#define SNTP_CHECK_RESPONSE 2
// Correct for the network delay to the time server.
#define SNTP_COMP_ROUNDTRIP 1
// Ask at once after start, then once an hour.
#define SNTP_STARTUP_DELAY 0
#define SNTP_UPDATE_DELAY 3600000
#define SNTP_GET_SYSTEM_TIME(sec, us) wifi_sta_sntp_get_time(&(sec), &(us))
#define SNTP_SET_SYSTEM_TIME_US(sec, us) wifi_sta_sntp_set_time((sec), (us))
void wifi_sta_sntp_get_time(uint32_t *sec, uint32_t *us);
void wifi_sta_sntp_set_time(uint32_t sec, uint32_t us);

#endif
