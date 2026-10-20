CC ?= cc
CFLAGS ?= -D_DEFAULT_SOURCE -std=c11 -O2 -Wall -Wextra -Werror
OUT ?= build

.PHONY: all test
all: $(OUT)/eapol-observer

$(OUT):
	mkdir -p $(OUT)

$(OUT)/eapol-observer: observer_main.c eapol_metadata.c eapol_metadata.h packet_address.h | $(OUT)
	$(CC) $(CFLAGS) observer_main.c eapol_metadata.c -o $@

test: | $(OUT)
	$(CC) $(CFLAGS) test_metadata.c eapol_metadata.c -o $(OUT)/test-metadata
	$(CC) $(CFLAGS) test_packet_address.c -o $(OUT)/test-address
	$(CC) $(CFLAGS) observer_main.c eapol_metadata.c test_cli_guard.c -Wl,--wrap=socket -Wl,--wrap=if_nametoindex -o $(OUT)/test-cli
	$(OUT)/test-metadata
	$(OUT)/test-address
	$(OUT)/test-cli --help
