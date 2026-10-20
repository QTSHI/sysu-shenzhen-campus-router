/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef EAPOL_METADATA_H
#define EAPOL_METADATA_H
#include <stddef.h>
#include <stdint.h>

/* Ethernet(14) + EAPOL(4) + EAP code/id/length(4) + optional EAP type(1).
 * This is below the 32-byte ceiling and never receives Identity/MD5 body bytes. */
#define OBSERVER_CAPTURE_BYTES 23
#define OBSERVER_MAX_SECONDS 300

typedef struct {
    unsigned int version;
    unsigned int packet_type;
    unsigned int body_length;
    int eap_present;
    unsigned int eap_code;
    unsigned int eap_id;
    unsigned int eap_length;
    int eap_type_present;
    unsigned int eap_type;
} eapol_metadata;

/* 1 = metadata, 0 = other EtherType, -1 = malformed/truncated. No payload copies. */
int parse_eapol_metadata(const uint8_t *prefix, size_t captured, size_t wire_length,
                         eapol_metadata *result);
int format_eapol_metadata(char *output, size_t capacity, uint64_t sequence, uint64_t elapsed_ms,
                         int outgoing, size_t wire_length, const eapol_metadata *record);
int observer_arguments(int argc, char **argv, const char **interface, unsigned int *seconds);
#endif
