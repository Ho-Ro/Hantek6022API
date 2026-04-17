#!/usr/bin/env python3
"""
Flash firmware into Hantek 6022 device.

Upload either default firmware when called without arguments
(depending on device VID/PID), or firmware-DSO6022BE or
firmware-DSO6022BL with provided VID:PID.
"""

import sys
import argparse
from PyHT6022.LibUsbScope import Oscilloscope
from PyHT6022.Firmware import dso6022be_firmware, dso6022bl_firmware


def parse_arguments(args=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='upload_firmware_6022.py',
        description='Upload firmware to Hantek6022 devices with different VID:PID'
    )
    parser.add_argument(
        '-V', '--VID',
        type=lambda x: int(x, 16),
        default=0,
        help='set vendor id (hex)'
    )
    parser.add_argument(
        '-P', '--PID',
        type=lambda x: int(x, 16),
        default=0,
        help='set product id (hex)'
    )
    fw_group = parser.add_mutually_exclusive_group()
    fw_group.add_argument(
        '--be', '--6022be',
        action='store_true',
        help='use DSO-6022BE firmware'
    )
    fw_group.add_argument(
        '--bl', '--6022bl',
        action='store_true',
        help='use DSO-6022BL firmware'
    )

    return parser.parse_args(args)


def create_scope(options):
    """Create and return an Oscilloscope instance based on options."""
    if not options.VID and not options.PID:
        return Oscilloscope()
    elif options.VID and options.PID and (options.be or options.bl):
        return Oscilloscope(options.VID, options.PID)
    else:
        print('--VID and --PID and one of --be or --bl must be provided', file=sys.stderr)
        sys.exit(1)


def select_firmware(options):
    """Select the appropriate firmware based on options."""
    if options.be:
        return dso6022be_firmware, 'DSO-6022BE'
    elif options.bl:
        return dso6022bl_firmware, 'DSO-6022BL'
    else:
        return None, 'default'


def main():
    """Upload firmware to Hantek 6022 device."""
    options = parse_arguments()

    scope = create_scope(options)

    if not scope.setup():
        print('scope setup error - no device?', file=sys.stderr)
        sys.exit(-1)

    if not scope.open_handle():
        print('scope open error - no device?', file=sys.stderr)
        sys.exit(-1)

    firmware, name = select_firmware(options)
    print(f'upload {name} firmware')

    if firmware:
        scope.flash_firmware(firmware)
    else:
        scope.flash_firmware()

    print(f'FW version {hex(scope.get_fw_version())}')
    print(f'Serial number {scope.get_serial_number_string()}')

    scope.close_handle()


if __name__ == "__main__":
    main()
