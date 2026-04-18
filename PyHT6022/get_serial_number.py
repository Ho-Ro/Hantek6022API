#!/usr/bin/env python3
"""
Get serial number from Hantek 6022BE/BL oscilloscope.
"""

import sys
from PyHT6022.LibUsbScope import Oscilloscope


def print_help():
    """Print simple help message."""
    print("Usage: get_serial_number_6022 - get serial number from Hantek 6022BE/BL oscilloscope")


def main():
    """Get and print the serial number of the oscilloscope."""
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print_help()
        return 0

    try:
        scope = Oscilloscope()
        scope.setup()
        scope.open_handle()

        if not scope.is_device_firmware_present:
            scope.flash_firmware()

        serial = scope.get_serial_number_string()
        if serial:
            print(serial)
        else:
            print("Could not read serial number", file=sys.stderr)
            return 1

        scope.close_handle()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
