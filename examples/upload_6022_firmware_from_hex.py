#!/usr/bin/python3

# flash the firmware from hex file


from PyHT6022.LibUsbScope import Oscilloscope
from sys import argv

if len( argv ) > 1:
	firmware = argv[ 1 ]
	scope = Oscilloscope()
	scope.setup()
	scope.open_handle()
	scope.flash_firmware_from_hex( firmware )
	print( "FW version", hex( scope.get_fw_version() ) )
	scope.close_handle()
else:
	print( "usage: " + argv[0] + " path_to_hexfile" )
