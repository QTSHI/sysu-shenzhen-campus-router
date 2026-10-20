/* SPDX-License-Identifier: GPL-3.0-only */
#include "eapol_metadata.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned int tests = 0;
#define CHECK(expression) do { assert(expression); ++tests; } while (0)

static void set16(uint8_t *p, unsigned int value) { p[0] = value >> 8; p[1] = value & 255; }
static void frame(uint8_t *bytes, unsigned int type, unsigned int body_length) {
    memset(bytes, 0xa5, OBSERVER_CAPTURE_BYTES);
    set16(bytes + 12, 0x888e);
    bytes[14] = 1;
    bytes[15] = (uint8_t)type;
    set16(bytes + 16, body_length);
}

static void check_parse_and_privacy(void) {
    uint8_t bytes[32];
    eapol_metadata record = {0};
    char json[512], first_json[512];
    frame(bytes, 0, 14);
    bytes[18] = 2; bytes[19] = 7; set16(bytes + 20, 14); bytes[22] = 1;
    memcpy(bytes + 23, "SECRET_ID", 9);
    CHECK(parse_eapol_metadata(bytes, OBSERVER_CAPTURE_BYTES, 60, &record) == 1);
    CHECK(record.version == 1 && record.packet_type == 0 && record.body_length == 14);
    CHECK(record.eap_present && record.eap_code == 2 && record.eap_id == 7 &&
          record.eap_length == 14 && record.eap_type_present && record.eap_type == 1);
    CHECK(format_eapol_metadata(json, sizeof(json), 1, 42, 1, 60, &record) > 0);
    CHECK(strcmp(json, "{\"seq\":1,\"elapsed_ms\":42,\"direction\":\"out\",\"wire_length\":60,"
          "\"eapol_version\":1,\"eapol_type\":0,\"eapol_body_length\":14,\"eap_code\":2,"
          "\"eap_id\":7,\"eap_length\":14,\"eap_type\":1}\n") == 0);
    CHECK(strstr(json, "SECRET_ID") == NULL && strstr(json, "a5") == NULL &&
          strstr(json, "mac") == NULL && strstr(json, "payload") == NULL);
    strcpy(first_json, json);
    /* Same header and wire length, entirely different MAC and Identity bytes. */
    memset(bytes, 0x5a, 12); memcpy(bytes + 23, "OTHERUSER", 9);
    CHECK(parse_eapol_metadata(bytes, OBSERVER_CAPTURE_BYTES, 60, &record) == 1);
    CHECK(format_eapol_metadata(json, sizeof(json), 1, 42, 1, 60, &record) > 0);
    CHECK(strstr(json, "OTHERUSER") == NULL && strstr(json, "5a") == NULL);
    CHECK(strcmp(first_json, json) == 0);
    /* MD5 request needs only its type byte, even though the challenge is not captured. */
    frame(bytes, 0, 26); bytes[18] = 1; bytes[19] = 99; set16(bytes + 20, 26); bytes[22] = 4;
    CHECK(parse_eapol_metadata(bytes, 23, 60, &record) == 1);
    CHECK(record.eap_type == 4 && record.eap_id == 99);
    /* Success header is length four; Ethernet padding is not part of EAP. */
    frame(bytes, 0, 4); bytes[18] = 3; bytes[19] = 99; set16(bytes + 20, 4);
    CHECK(parse_eapol_metadata(bytes, 22, 60, &record) == 1);
    CHECK(record.eap_code == 3 && !record.eap_type_present && record.eap_length == 4);
    bytes[18] = 4;
    CHECK(parse_eapol_metadata(bytes, 22, 60, &record) == 1 && record.eap_code == 4);
    frame(bytes, 1, 0);
    CHECK(parse_eapol_metadata(bytes, 18, 60, &record) == 1 && !record.eap_present);
    CHECK(format_eapol_metadata(json, sizeof(json), 2, 100, 0, 60, &record) > 0);
    CHECK(strstr(json, "\"eap_code\":null,\"eap_id\":null,\"eap_length\":null,\"eap_type\":null") != NULL);
    frame(bytes, 3, 100);
    CHECK(parse_eapol_metadata(bytes, OBSERVER_CAPTURE_BYTES, 118, &record) == 1 && !record.eap_present);
}

static void check_boundaries(void) {
    uint8_t bytes[OBSERVER_CAPTURE_BYTES];
    eapol_metadata record = {0};
    size_t length;
    frame(bytes, 0, 5); bytes[18] = 1; bytes[19] = 1; set16(bytes + 20, 5); bytes[22] = 1;
    CHECK(parse_eapol_metadata(NULL, 23, 60, &record) == -1);
    CHECK(parse_eapol_metadata(bytes, 23, 60, NULL) == -1);
    CHECK(parse_eapol_metadata(bytes, 33, 60, &record) == -1);
    CHECK(parse_eapol_metadata(bytes, 23, 22, &record) == -1);
    for (length = 0; length < 23; ++length)
        CHECK(parse_eapol_metadata(bytes, length, 60, &record) == -1);
    CHECK(parse_eapol_metadata(bytes, 23, 23, &record) == 1);
    set16(bytes + 16, 43); CHECK(parse_eapol_metadata(bytes, 23, 60, &record) == -1);
    set16(bytes + 16, 3); CHECK(parse_eapol_metadata(bytes, 23, 60, &record) == -1);
    set16(bytes + 16, 5); set16(bytes + 20, 3);
    CHECK(parse_eapol_metadata(bytes, 23, 60, &record) == -1);
    set16(bytes + 20, 6); CHECK(parse_eapol_metadata(bytes, 23, 60, &record) == -1);
    set16(bytes + 20, 4); CHECK(parse_eapol_metadata(bytes, 23, 60, &record) == -1);
    set16(bytes + 12, 0x0800); CHECK(parse_eapol_metadata(bytes, 14, 60, &record) == 0);
    { char tiny[1];
      CHECK(format_eapol_metadata(NULL, 0, 0, 0, 0, 0, &record) == -1);
      CHECK(format_eapol_metadata(tiny, 0, 0, 0, 0, 0, &record) == -1);
      CHECK(format_eapol_metadata(tiny, 1, 0, 0, 0, 0, &record) == -1);
      CHECK(format_eapol_metadata(tiny, 1, 0, 0, 0, 0, NULL) == -1);
    }
    /* ASan/UBSan exercise actual C parser against every short captured length. */
    frame(bytes, 0, 5); bytes[18] = 1; bytes[19] = 1; set16(bytes + 20, 5); bytes[22] = 1;
    for (length = 0; length <= OBSERVER_CAPTURE_BYTES; ++length) {
        uint8_t *exact = malloc(length ? length : 1);
        CHECK(exact != NULL);
        if (length) memcpy(exact, bytes, length);
        (void)parse_eapol_metadata(exact, length, length, &record);
        free(exact);
    }
}

static int arguments(char **argv, int argc) {
    const char *interface = NULL;
    unsigned int seconds = 0;
    int result = observer_arguments(argc, argv, &interface, &seconds);
    if (result == 1) CHECK(interface != NULL && seconds >= 1 && seconds <= 300);
    return result;
}
static void check_arguments(void) {
    char *default_argv[] = {"test"}; CHECK(arguments(default_argv, 1) == 0);
    char *help[] = {"test", "--help"}; CHECK(arguments(help, 2) == 0);
    char *valid[] = {"test", "--interface", "eth0.1", "--seconds", "300"}; CHECK(arguments(valid, 5) == 1);
    valid[4] = "1"; CHECK(arguments(valid, 5) == 1);
    valid[4] = "301"; CHECK(arguments(valid, 5) == -1);
    valid[4] = "0"; CHECK(arguments(valid, 5) == -1);
    valid[4] = "-1"; CHECK(arguments(valid, 5) == -1);
    valid[4] = "1x"; CHECK(arguments(valid, 5) == -1);
    valid[4] = "1"; valid[2] = "any"; CHECK(arguments(valid, 5) == -1);
    valid[2] = ""; CHECK(arguments(valid, 5) == -1);
    valid[2] = "../../eth0"; CHECK(arguments(valid, 5) == -1);
    valid[2] = "eth0\n"; CHECK(arguments(valid, 5) == -1);
    valid[2] = "1234567890123456"; CHECK(arguments(valid, 5) == -1);
    valid[2] = "123456789012345"; CHECK(arguments(valid, 5) == 1);
    CHECK(arguments(valid, 3) == -1);
    char *duplicate[] = {"test", "--interface", "eth0.1", "--seconds", "1", "--interface", "eth0.2"};
    CHECK(arguments(duplicate, 7) == -1);
    char *duplicate_seconds[] = {"test", "--interface", "eth0.1", "--seconds", "1", "--seconds", "2"};
    CHECK(arguments(duplicate_seconds, 7) == -1);
    char *missing[] = {"test", "--interface"}; CHECK(arguments(missing, 2) == -1);
    char *help_with_capture[] = {"test", "--help", "--interface", "eth0.1", "--seconds", "1"};
    CHECK(arguments(help_with_capture, 6) == -1);
}

int main(void) {
    check_parse_and_privacy(); check_boundaries(); check_arguments();
    printf("PASS: %u C assertions; synthetic memory only; no network calls\n", tests);
    return 0;
}
