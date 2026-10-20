/* SPDX-License-Identifier: GPL-3.0-only */
#define _POSIX_C_SOURCE 200809L
#include "eapol_metadata.h"
#include "packet_address.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <net/if_arp.h>
#include <net/if.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted = 0;
static void stop_signal(int number) { (void)number; interrupted = 1; }
static int monotonic_ms(uint64_t *value) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0)
        return -1;
    *value = (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000;
    return 0;
}
static void usage(void) {
    fputs("Passive EAPOL header metadata observer\n"
          "Usage: eapol-observer --interface IFACE --seconds 1..300\n"
          "Default/--help only displays this help. No credentials or payload are output.\n", stdout);
}

int main(int argc, char **argv) {
    const char *interface = NULL;
    unsigned int seconds = 0, index;
    int parsed_args = observer_arguments(argc, argv, &interface, &seconds);
    int fd = -1, exit_code = 0, saved_stdout_flags = -1;
    uint64_t start, now, deadline, received = 0, emitted = 0, ignored = 0, malformed = 0;
    struct sockaddr_ll bound;
    struct sigaction action;
    if (parsed_args == 0) { usage(); return 0; }
    if (parsed_args < 0) { fputs("observer_error arguments\n", stderr); return 2; }
    index = if_nametoindex(interface);
    if (index == 0 || index > INT32_MAX) {
        fputs("observer_error interface\n", stderr); return 3;
    }
    if (monotonic_ms(&start) < 0) {
        fputs("observer_error clock\n", stderr); return 3;
    }
    deadline = start + (uint64_t)seconds * 1000;
    memset(&action, 0, sizeof(action));
    action.sa_handler = stop_signal;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) != 0 || sigaction(SIGTERM, &action, NULL) != 0 ||
        sigaction(SIGHUP, &action, NULL) != 0) {
        fputs("observer_error signals\n", stderr); return 3;
    }
    action.sa_handler = SIG_IGN;
    if (sigaction(SIGPIPE, &action, NULL) != 0) {
        fputs("observer_error signals\n", stderr); return 3;
    }
    /* A zero protocol prevents receipt on any interface before bind succeeds. */
    fd = socket(AF_PACKET, SOCK_RAW | SOCK_CLOEXEC, 0);
    if (fd < 0) { fputs("observer_error socket\n", stderr); return 4; }
    memset(&bound, 0, sizeof(bound));
    bound.sll_family = AF_PACKET;
    bound.sll_ifindex = (int)index;
    bound.sll_protocol = htons(ETH_P_PAE);
    if (bind(fd, (struct sockaddr *)&bound, sizeof(bound)) != 0) {
        fputs("observer_error bind\n", stderr); exit_code = 4; goto done;
    }
    {
        struct sockaddr_ll actual;
        socklen_t length = sizeof(actual);
        memset(&actual, 0, sizeof(actual));
        if (getsockname(fd, (struct sockaddr *)&actual, &length) != 0 || !observer_packet_address_valid(&actual, length, index)) {
            fputs("observer_error bind_verification\n", stderr); exit_code = 4; goto done;
        }
    }
    /* A stalled consumer must not prolong the finite observation window.
     * Preserve the inherited descriptor's flags and restore them before return. */
    saved_stdout_flags = fcntl(STDOUT_FILENO, F_GETFL);
    if (saved_stdout_flags < 0 ||
        fcntl(STDOUT_FILENO, F_SETFL, saved_stdout_flags | O_NONBLOCK) < 0) {
        fputs("observer_error output_mode\n", stderr); exit_code = 3; goto done;
    }
    while (!interrupted) {
        struct pollfd poll_fd = {fd, POLLIN, 0};
        int poll_result;
        if (monotonic_ms(&now) < 0) {
            fputs("observer_error clock\n", stderr); exit_code = 5; break;
        }
        if (now >= deadline)
            break;
        poll_result = poll(&poll_fd, 1, (int)(deadline - now));
        if (poll_result < 0) {
            if (errno == EINTR) continue;
            fputs("observer_error poll\n", stderr); exit_code = 5; break;
        }
        if (poll_result == 0) continue;
        if ((poll_fd.revents & (POLLERR | POLLHUP | POLLNVAL)) || !(poll_fd.revents & POLLIN)) {
            fputs("observer_error poll_state\n", stderr); exit_code = 5; break;
        }
        {
            uint8_t prefix[OBSERVER_CAPTURE_BYTES] = {0};
            struct sockaddr_ll sender;
            struct iovec iov = {prefix, sizeof(prefix)};
            struct msghdr message;
            ssize_t wire_length;
            eapol_metadata record;
            int parse_result, outgoing;
            memset(&sender, 0, sizeof(sender));
            memset(&message, 0, sizeof(message));
            message.msg_name = &sender;
            message.msg_namelen = sizeof(sender);
            message.msg_iov = &iov;
            message.msg_iovlen = 1;
            wire_length = recvmsg(fd, &message, MSG_TRUNC | MSG_DONTWAIT);
            if (wire_length < 0) {
                if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK) continue;
                fputs("observer_error receive\n", stderr); exit_code = 5; break;
            }
            ++received;
            if (!observer_packet_address_valid(&sender, message.msg_namelen, index) ||
                sender.sll_hatype != ARPHRD_ETHER ||
                sender.sll_pkttype > PACKET_OUTGOING) {
                ++ignored; continue;
            }
            outgoing = sender.sll_pkttype == PACKET_OUTGOING;
            parse_result = parse_eapol_metadata(prefix,
                    (size_t)wire_length < sizeof(prefix) ? (size_t)wire_length : sizeof(prefix),
                    (size_t)wire_length, &record);
            if (parse_result == 0) { ++ignored; continue; }
            if (parse_result < 0) { ++malformed; continue; }
            if (monotonic_ms(&now) < 0) {
                fputs("observer_error clock\n", stderr); exit_code = 5; break;
            }
            if (now >= deadline || interrupted) break;
            {
                char json_line[512];
                int length = format_eapol_metadata(json_line, sizeof(json_line), emitted + 1,
                                now - start, outgoing, (size_t)wire_length, &record);
                if (length < 0 || write(STDOUT_FILENO, json_line, (size_t)length) != length) {
                    fputs("observer_error output\n", stderr); exit_code = 6; break;
                }
            }
            ++emitted;
        }
    }
done:
    if (fd >= 0) close(fd);
    if (saved_stdout_flags >= 0 && fcntl(STDOUT_FILENO, F_SETFL, saved_stdout_flags) < 0) {
        fputs("observer_error output_restore\n", stderr); exit_code = 6;
    }
    fprintf(stderr, "observer_counts received=%" PRIu64 " emitted=%" PRIu64
                    " ignored=%" PRIu64 " malformed=%" PRIu64 "\n",
                    received, emitted, ignored, malformed);
    return exit_code;
}
