#include "broker_find.h"

#include <string.h>

#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"

#include "lwip/pbuf.h"
#include "lwip/udp.h"

#include "beacon.h"
#include "config.h"

// Written by the receive callback in the lwIP context. Read with the async
// context lock held (cyw43_arch_lwip_begin).
static beacon_pick_t pick;
static broker_find_counts_t counts;

// lwIP calls this for every datagram on the beacon port, also during a scan
// window. It only reads: a broadcast is never acknowledged or answered, so
// nothing is transmitted because of it.
static void on_datagram(void *arg, struct udp_pcb *pcb, struct pbuf *p, const ip_addr_t *addr, u16_t port) {
    (void)arg;
    (void)pcb;
    (void)port;
    uint8_t data[BEACON_MAX_LEN];
    beacon_addr_t from;
    bool ok = false;
    if (p->tot_len <= sizeof(data)) {
        u16_t len = pbuf_copy_partial(p, data, p->tot_len, 0);
        // lwIP keeps the address in network byte order, which is a.b.c.d.
        u32_t raw = ip4_addr_get_u32(ip_2_ip4(addr));
        memcpy(from.ip, &raw, sizeof(from.ip));
        ok = beacon_verify(HASH_SALT, data, len, from.ip, &from.port);
    }
    pbuf_free(p);
    if (ok) {
        beacon_pick_heard(&pick, &from, to_ms_since_boot(get_absolute_time()));
        counts.heard++;
    } else {
        counts.rejected++;
    }
}

bool broker_find_init(void) {
    beacon_pick_init(&pick);
    cyw43_arch_lwip_begin();
    struct udp_pcb *pcb = udp_new_ip_type(IPADDR_TYPE_V4);
    bool ok = pcb != NULL && udp_bind(pcb, IP_ANY_TYPE, BEACON_UDP_PORT) == ERR_OK;
    if (ok) {
        udp_recv(pcb, on_datagram, NULL);
    } else if (pcb != NULL) {
        udp_remove(pcb);
    }
    cyw43_arch_lwip_end();
    return ok;
}

static void to_lwip(const beacon_addr_t *from, ip_addr_t *ip, uint16_t *port) {
    IP_ADDR4(ip, from->ip[0], from->ip[1], from->ip[2], from->ip[3]);
    *port = from->port;
}

bool broker_find_live(ip_addr_t *ip, uint16_t *port) {
    beacon_addr_t from;
    cyw43_arch_lwip_begin();
    bool found = beacon_pick_live(&pick, to_ms_since_boot(get_absolute_time()), &from);
    cyw43_arch_lwip_end();
    if (found) {
        to_lwip(&from, ip, port);
    }
    return found;
}

bool broker_find_last(ip_addr_t *ip, uint16_t *port) {
    beacon_addr_t from;
    cyw43_arch_lwip_begin();
    bool found = beacon_pick_last(&pick, &from);
    cyw43_arch_lwip_end();
    if (found) {
        to_lwip(&from, ip, port);
    }
    return found;
}

broker_find_counts_t broker_find_take_counts(void) {
    cyw43_arch_lwip_begin();
    broker_find_counts_t taken = counts;
    memset(&counts, 0, sizeof(counts));
    cyw43_arch_lwip_end();
    return taken;
}
