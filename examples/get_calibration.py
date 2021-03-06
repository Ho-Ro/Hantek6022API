#!/usr/bin/python3

__author__ = 'Jochen Hoenicke'

from PyHT6022.LibUsbScope import Oscilloscope

scope = Oscilloscope()
scope.setup()
scope.open_handle()
calibration = scope.get_calibration_values( 48 )
scope.close_handle()

# print( calibration )
for x in calibration:
    print( hex(x), end=" " )
