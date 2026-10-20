/* SPDX-License-Identifier: GPL-3.0-only */
#include "eapol_metadata.h"
#include <ctype.h>
#include <inttypes.h>
#include <limits.h>
#include <net/if.h>
#include <stdio.h>
#include <string.h>

static unsigned int be16(const uint8_t *p) {
    return ((unsigned int)p[0] << 8) | p[1];
}

int parse_eapol_metadata(const uint8_t *prefix, size_t captured, size_t wire_length,
                         eapol_metadata *result) {
    eapol_metadata parsed = {0};
    if (prefix == NULL || result == NULL || captured > OBSERVER_CAPTURE_BYTES ||
        captured > wire_length || captured < 14)
        return -1;
    if (be16(prefix + 12) != 0x888e)
        return 0;
    if (captured < 18)
        return -1;
    parsed.version = prefix[14];
    parsed.packet_type = prefix[15];
    parsed.body_length = be16(prefix + 16);
    if ((size_t)parsed.body_length > wire_length - 18)
        return -1;
    if (parsed.packet_type == 0) {
        if (parsed.body_length < 4 || captured < 22)
            return -1;
        parsed.eap_present = 1;
        parsed.eap_code = prefix[18];
        parsed.eap_id = prefix[19];
        parsed.eap_length = be16(prefix + 20);
        if (parsed.eap_length < 4 || parsed.eap_length > parsed.body_length)
            return -1;
        if (parsed.eap_code == 1 || parsed.eap_code == 2) {
            if (parsed.eap_length < 5 || captured < 23)
                return -1;
            parsed.eap_type_present = 1;
            parsed.eap_type = prefix[22];
        }
    }
    *result = parsed;
    return 1;
}

int format_eapol_metadata(char *output, size_t capacity, uint64_t sequence, uint64_t elapsed_ms,
                         int outgoing, size_t wire_length, const eapol_metadata *record) {
    char code[16] = "null", id[16] = "null", length[16] = "null", type[16] = "null";
    int result;
    if (output == NULL || capacity == 0 || record == NULL)
        return -1;
    if (record->eap_present) {
        (void)snprintf(code, sizeof(code), "%u", record->eap_code);
        (void)snprintf(id, sizeof(id), "%u", record->eap_id);
        (void)snprintf(length, sizeof(length), "%u", record->eap_length);
        if (record->eap_type_present)
            (void)snprintf(type, sizeof(type), "%u", record->eap_type);
    }
    result = snprintf(output, capacity, "{\"seq\":%" PRIu64 ",\"elapsed_ms\":%" PRIu64
                      ",\"direction\":\"%s\",\"wire_length\":%zu,\"eapol_version\":%u,"
                      "\"eapol_type\":%u,\"eapol_body_length\":%u,\"eap_code\":%s,"
                      "\"eap_id\":%s,\"eap_length\":%s,\"eap_type\":%s}\n",
                      sequence, elapsed_ms, outgoing ? "out" : "in", wire_length,
                      record->version, record->packet_type, record->body_length, code, id, length, type);
    if (result < 0 || (size_t)result >= capacity)
        return -1;
    return result;
}

/* 0 = explicit help, 1 = valid capture request, -1 = fixed usage error. */
int observer_arguments(int argc, char **argv, const char **interface, unsigned int *seconds) {
    const char *name = NULL;
    unsigned int duration = 0;
    int i, have_seconds = 0;
    if (argc == 1 || (argc == 2 && strcmp(argv[1], "--help") == 0))
        return 0;
    for (i = 1; i < argc; i += 2) {
        const char *value;
        size_t j, length;
        if (i + 1 >= argc)
            return -1;
        value = argv[i + 1];
        length = strlen(value);
        if (strcmp(argv[i], "--interface") == 0) {
            if (name != NULL || length == 0 || length >= IFNAMSIZ)
                return -1;
            for (j = 0; j < length; ++j) {
                unsigned char c = (unsigned char)value[j];
                if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                      (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-' || c == ':'))
                    return -1;
            }
            if (strcmp(value, ".") == 0 || strcmp(value, "..") == 0 || strcmp(value, "any") == 0)
                return -1;
            name = value;
        } else if (strcmp(argv[i], "--seconds") == 0) {
            if (have_seconds || length == 0 || length > 3)
                return -1;
            for (j = 0; j < length; ++j) {
                if (value[j] < '0' || value[j] > '9')
                    return -1;
                duration = duration * 10 + (unsigned int)(value[j] - '0');
            }
            if (duration == 0 || duration > OBSERVER_MAX_SECONDS)
                return -1;
            have_seconds = 1;
        } else {
            return -1;
        }
    }
    if (name == NULL || !have_seconds)
        return -1;
    *interface = name;
    *seconds = duration;
    return 1;
}
