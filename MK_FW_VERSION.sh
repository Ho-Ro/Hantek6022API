#!/bin/sh

# extract version (MAJOR and minor) from FW source
# version is stored as byte swapped word (0xmmMM)
# format as uint16_t 0xMMmm
# write header file for OpenHantek6022


MINORMAJOR=$(grep -Eo 'FIRMWARE_VERSION[[:space:]]+=[[:space:]]+0x[0-9]{4}' Firmware/DSO6022BE/descriptor.inc | cut -dx -f2)

MINOR=`echo $MINORMAJOR | cut -b1-2`
MAJOR=`echo $MINORMAJOR | cut -b3-4`

FWversion=PyHT6022/Firmware/version.py

echo "// SPDX-License-Identifier: GPL-3.0-or-later"
echo
echo "#pragma once"
echo
echo "#include <stdint.h>"
echo
echo "// Do not edit, this file will be recreated with every build."
echo
echo "const uint16_t DSO602x_FW_VER = 0x${MAJOR}${MINOR};"
echo
echo "// Firmware/DSO6022BE/descriptor.inc: $(grep -Eo 'FIRMWARE_VERSION[[:space:]]+=[[:space:]]+0x[0-9]{4}' Firmware/DSO6022BE/descriptor.inc)"
echo "// pyproject.toml: $(grep -Eo 'version[[:space:]]+=[[:space:]]+"[0-9]{1,2}.[0-9]{1,2}.[0-9]{1,2}"' pyproject.toml)"
echo "// debian/changelog: $(head -1 debian/changelog)"
echo "# Do not edit, this file will be recreated with every build." > $FWversion
echo firmware_version = 0x${MAJOR}${MINOR} >> $FWversion
echo
