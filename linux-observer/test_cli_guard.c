/* SPDX-License-Identifier: GPL-3.0-only */
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <net/if.h>

int __wrap_socket(int domain, int type, int protocol) {
    (void)domain; (void)type; (void)protocol;
    fputs("OFFLINE_GUARD: forbidden socket call\n", stderr);
    exit(99);
}
unsigned int __wrap_if_nametoindex(const char *name) {
    (void)name;
    fputs("OFFLINE_GUARD: forbidden interface lookup\n", stderr);
    exit(99);
}
