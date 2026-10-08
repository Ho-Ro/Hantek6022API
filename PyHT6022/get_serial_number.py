#!/usr/bin/env python3
"""
Get serial number from Hantek 6022BE/BL oscilloscope.

Prints the serial number to stdout, product name and firmware version
to stderr. Example:

    get_serial_number_6022 2>/dev/null
    CF81BA1F3532
"""

import sys

from PyHT6022.LibUsbScope import Oscilloscope


def print_help():
    """Print simple help message."""
    print("Usage: get_serial_number_6022 - get serial number from Hantek 6022BE/BL oscilloscope")


def main(args=None):
    """
    Read and print the device identification.
    :param args: Command line arguments, default: sys.argv.
    :return: Exit status.
    """
    if args is None:
        args = sys.argv[1:]
    if args and args[0] in ('-h', '--help'):
        print_help()
        return 0

    try:
        scope = Oscilloscope()
        scope.setup()
        if not scope.open_handle():
            print("Error: no device?", file=sys.stderr)
            return 1

        if not scope.is_device_firmware_present:
            print('Upload firmware...', file=sys.stderr)
            scope.flash_firmware()

        serial = scope.get_serial_number_string()
        if not serial:
            print("Could not read serial number", file=sys.stderr)
            return 1
        print(serial)
        sys.stdout.flush()

        product = scope.get_product_string()
        if product:
            print(f'product name: {product}', file=sys.stderr)
        version = scope.get_fw_version()
        if version:
            print(f'FW version: {hex(version)}', file=sys.stderr)

        scope.close_handle()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
