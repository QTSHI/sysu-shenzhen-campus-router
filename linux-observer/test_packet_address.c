/* SPDX-License-Identifier: GPL-3.0-only */
#include "packet_address.h"
#include <assert.h>
#include <net/if_arp.h>
#include <stdio.h>
#include <string.h>

static struct sockaddr_ll valid(void) {
    struct sockaddr_ll v;
    memset(&v,0,sizeof(v));
    v.sll_family=AF_PACKET;v.sll_ifindex=7;v.sll_protocol=htons(ETH_P_PAE);
    v.sll_hatype=ARPHRD_ETHER;v.sll_halen=6;
    return v;
}
int main(void) {
    struct sockaddr_ll a=valid();
    assert(offsetof(struct sockaddr_ll,sll_addr)==12);
    assert(sizeof(a)==20);
    /* Actual kernel tail versus full allocated address are both legal. */
    assert(observer_packet_address_valid(&a,18,7));
    assert(observer_packet_address_valid(&a,19,7));
    assert(observer_packet_address_valid(&a,20,7));
    for(socklen_t n=0;n<18;n++) assert(!observer_packet_address_valid(&a,n,7));
    assert(!observer_packet_address_valid(&a,21,7));
    assert(!observer_packet_address_valid(&a,(socklen_t)-1,7));
    a.sll_halen=9;assert(!observer_packet_address_valid(&a,20,7));
    a=valid();a.sll_halen=8;
    assert(!observer_packet_address_valid(&a,18,7));
    assert(observer_packet_address_valid(&a,20,7));
    a=valid();a.sll_family=AF_INET;assert(!observer_packet_address_valid(&a,18,7));
    a=valid();a.sll_ifindex=8;assert(!observer_packet_address_valid(&a,18,7));
    a=valid();a.sll_protocol=htons(ETH_P_IP);assert(!observer_packet_address_valid(&a,18,7));
    puts("packet-address boundary/tamper tests passed; no sockets opened");
    return 0;
}
