#!/bin/sh
# GPL-3.0-only. Local compilation only; no installation or authentication.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE=$ROOT/build/minieap-983fd4a5851d4a344fab92666c5cdb83f26b2294
test -f "$SOURCE/Makefile"
CC=${CC:-arm-linux-gnueabi-gcc}
make -C "$SOURCE" -j2 minieap CC="$CC" PLUGIN_MODULES=if_impl_sockraw \
 ENABLE_DEBUG=false ENABLE_ICONV=false ENABLE_GBCONV=false STATIC_BUILD=true \
 CUSTOM_CFLAGS='-Os -march=armv7-a -mfloat-abi=soft -fno-strict-aliasing'
printf '%s\n' 'Built only. Verify ELF/ABI and local security gates before any deployment.'
