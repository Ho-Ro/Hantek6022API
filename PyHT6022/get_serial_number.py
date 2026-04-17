#!/usr/bin/env python3
"""
Minimal version - Get serial number from Hantek 6022BE/BL oscilloscope.
"""

import sys
from PyHT6022.LibUsbScope import Oscilloscope


def main():
    """Entry point for console script - minimal version."""
    try:
        scope = Oscilloscope()
        scope.setup()
        scope.open_handle()

        # Upload firmware if needed
        if not scope.is_device_firmware_present:
            scope.flash_firmware()

        # Get and print serial number
        serial = scope.get_serial_number()
        print(serial)

        scope.close_handle()
        return 0

    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
