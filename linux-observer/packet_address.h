/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef SYSU_PACKET_ADDRESS_H
#define SYSU_PACKET_ADDRESS_H
#include <arpa/inet.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <stddef.h>
#include <sys/socket.h>

/* sockaddr_ll's eight-byte address array has a variable-length kernel tail.
 * Validate all fields before use; never read or output the address bytes. */
static inline int observer_packet_address_valid(const struct sockaddr_ll *address,
                                               socklen_t returned_length,
                                               unsigned int expected_index) {
    const size_t header=offsetof(struct sockaddr_ll,sll_addr);
    if(returned_length<header || returned_length>sizeof(*address)) return 0;
    if(address->sll_halen>sizeof(address->sll_addr) ||
       returned_length<header+(size_t)address->sll_halen) return 0;
    return address->sll_family==AF_PACKET &&
           address->sll_ifindex==(int)expected_index &&
           address->sll_protocol==htons(ETH_P_PAE);
}
#endif
