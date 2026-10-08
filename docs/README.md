# Reverse Engineering this Oscilloscope

One of the more unfortunate things about this scope as it comes stock is that there is no support for Linux, and
the drivers, while they have an SDK, are essentially binary blobs. We think that we can do better, and the goal
is thus to be able to write an open source driver that can be used on Linux (or BSD, Mac OS X, or Windows, if you're
into that) to get more functionality out of this device. 

Robert reverse engineered this scope by using the Windows SDK in a Windows VM, and watching USB traces on his Linux
host machine.

The following USB URB control commands map as follows:

| Oscilloscope Command | bRequest Value | Other Notes                                                            |
|----------------------|----------------|------------------------------------------------------------------------|
| Set CH0 voltage range|      0xE0      | Parameter: 1,2,5,10 (Gain x1: 5V, x2: 2.5V, x5: 1V, x10: 500mV).       |
| Set CH1 voltage range|      0xE1      | Parameter: 1,2,5,10 (Gain x1: 5V, x2: 2.5V, x5: 1V, x10: 500mV).       |
| Set Sampling Rate    |      0xE2      | Parameter:                                                             |
|                      |                |   48, 30, 24, 16, 15, 12, 10, 8, 6, 5, 4, 3, 2, 1 (MS/s)               |
|                      |                |   and 150, 140, 120, 110, 106, 105, 104, 102                           |
|                      |                |   (i.e. 500, 400, 200, 100, 64, 50, 40, 20 kS/s).                      |
| Trigger Oscilloscope |      0xE3      | Clear the FIFO on the FX2LP                                            |
| Set Channel Number   |      0xE4      | Parameter: 1 (transfer only CH1), 2 (transfer CH1 and CH2)             |
| Set AC_DC coupling *)|      0xE5      | Parameter: 0x00: AC/AC, 0x01: AC/DC, 0x10: DC/AC, 0x11: DC/DC          |
| *) with [HW modification](HANTEK6022_AC_Modification.pdf)                                                      |
| Set Calibration Out  |      0xE6      | Parameter freq:                                                        |
|                      |                |   0 -> 100 Hz (be compatible with sigrok FW)                           |
|                      |                |   1..100 -> 1..100 kHz                                                 |
|                      |                |   101..102 -> do not use                                               |
|                      |                |   103 -> 32 Hz (lowest possible calfreq due to 16bit HW timer2)        |
|                      |                |   104..200 -> 40..1000 Hz ( calfreq = 10*(freq-100) )                  |
|                      |                |   201..255 -> 100..5500 Hz ( calfreq = 100*(freq-200) )                |
| Read/Write EEPROM    |      0xA2      | Read or write the eeprom built into the scope.                         |
| Read/Write Firmware  |      0xA0      | Read or write the scope firmware. Must be done on scope initialization |

All commands are sent with index = 0x00, the calibration commands are sent with value 0x08 (offset into eeprom), the 0xEx requests are sent
with value 0x00, and the value for R/W command is dependent on the Cypress protocol for interacting with the firmware.

Additionally, a bulk read from end point 0x86 reads the current contents of the FIFO, which the ADC is filling. The
reference Python libusb code should give further insight into the means for which to interact with the device.


## Custom, modified and stock firmware

The Hantek 6022BE / BL uses a Cypress CY7C68013A (EZUSB FX2LP) processor with embedded 8051 core.
As the firmware is uploaded into RAM on every device initialisation, it is possible to use own firmware
instead of the Hantek version in order to get better performance from the device.
The custom version provides also alternate USB settings that use [isochronous transfer](https://community.cypress.com/docs/DOC-11853) mode instead of bulk transfer.
The fastest iso mode allows a reliable transfer of up to 20 MB/s, while the bulk mode allows a transfer rate of up to 30 MB/s,
although with some skipped data blocks at this fast speed. OpenHantek6022 currently only supports the bulk mode.

By default the Python reference library will load ***custom_BE*** (or ***custom_BL***) firmware into the device.
I took the sigrok branch and backported it to provide default Hantek VID/PID,
added eeprom access and created a ***custom_BL*** variant for 6022BL.
The eeprom access allows to write persistent calibration values directly into the scope.
[OpenHantek6022](https://github.com/OpenHantek/OpenHantek6022) uses these firmware variants 
and and takes advantage of the calibration values.
 
The ***custom*** firmware and the ***modded*** versions were originally written by
[jhoenicke](https://github.com/jhoenicke), to extract more performance out of the device.
The stock Hantek firmware is provided so that it may be uploaded and utilized as well.


## EEPROM

The device contains a 256 byte eeprom 24LC02B at I2C address 0x51.
The first 8 byte of the eeprom are important for startup.
They contain the initial USB vendor and device id to allow it
to bedetected before the firmware is flashed.
See chapter 3.4.2 of the ez-usb technical reference manual.
Example for 6022BE: `c0 b4 04 22 60 00 00 00`

The next 16 bytes (eeprom[8:23]) store offset calibration data for slow sample rates < 30 MS/s (also used by the windows SDK).

| Address |      Value |     Range |
|---------|------------|-----------|
|       8 | CH0 offset | 20 mV/div |
|       9 | CH1 offset | 20 mV/div |
|      10 | CH0 offset | 50 mV/div |
|      11 | CH1 offset | 50 mV/div |
|      .. |         .. |        .. |
|      22 | CH0 offset |   5 V/div |
|      23 | CH1 offset |   5 V/div |

The next 16 bytes (eeprom[24:39]) store offset calibration data for high sample rates >= 30 MS/s (also used by the windows SDK).

| Address |      Value |     Range |
|---------|------------|-----------|
|      24 | CH0 offset | 20 mV/div |
|      25 | CH1 offset | 20 mV/div |
|      .. |         .. |        .. |
|      36 | CH0 offset |   2 V/div |
|      37 | CH1 offset |   2 V/div |
|      38 | CH0 offset |   5 V/div |
|      39 | CH1 offset |   5 V/div |

A value of 0x80 means no correction, values > 0x80 shift the trace down, values < 0x80 shift it up.
With gain x1 one step equates about 40 mV

| Range      | Gain | Voltage / Step |
|------------|------|----------------|
|  20 mV/div |  x10 |           4 mV |
|  50 mV/div |  x10 |           4 mV |
| 100 mV/div |  x10 |           4 mV |
| 200 mV/div |   x5 |           8 mV |
| 500 mV/div |   x2 |          20 mV |
|    1 V/div |   x1 |          40 mV |
|    2 V/div |   x1 |          40 mV |
|    5 V/div |   x1 |          40 mV |

The next 16 bytes (eeprom[40:55]) are used to store gain calibration data (not used by the windows SDK).

| Address |    Value |     Range |
|---------|----------|-----------|
|      40 | CH0 gain | 20 mV/div |
|      41 | CH1 gain | 20 mV/div |
|      42 | CH0 gain | 50 mV/div |
|      43 | CH1 gain | 50 mV/div |
|      .. |       .. |        .. |
|      54 | CH0 gain |   5 V/div |
|      55 | CH1 gain |   5 V/div |

A value of 0x80 means no correction, factor = 1.0.
0x00 and 0xFF -> invalid, resulting in a factor of 1.0 (Factory setting is 0xFF)
Values >0x80 increase the trace on screen, values <0x80 make it smaller.

|      Value | Factor |    Result |
|------------|--------|-----------|
|       0x00 |  1.000 | invalid   |
| 0x80 - 125 |  0.750 | smallest  |
|         .. |     .. | ..        |
|   0x80 - 1 |  0.998 | smaller   |
|       0x80 |  1.000 | no change |
|    0x80 +1 |  1.002 | taller    |
|         .. |     .. | ..        |
| 0x80 + 125 |  1.250 | tallest   |
|       0xFF |  1.000 | invalid   |

The next 16 bytes (eeprom[56:71]) store sub-sample correction of offset calibration data for slow sample rates < 30 MS/s.

| Address |      Value   |     Range |
|---------|--------------|-----------|
|      56 | CH0 off frac | 20 mV/div |
|      57 | CH1 off frac | 20 mV/div |
|      58 | CH0 off frac | 50 mV/div |
|      59 | CH1 off frac | 50 mV/div |
|      .. |           .. |        .. |
|      70 | CH0 off frac |   5 V/div |
|      71 | CH1 off frac |   5 V/div |

The next 16 bytes (eeprom[72:87]) store sub-sample correction of offset calibration data for high sample rates >= 30 MS/s.

| Address |      Value   |     Range |
|---------|--------------|-----------|
|      72 | CH0 off frac | 20 mV/div |
|      73 | CH1 off frac | 20 mV/div |
|      .. |           .. |        .. |
|      84 | CH0 off frac |   2 V/div |
|      85 | CH1 off frac |   2 V/div |
|      86 | CH0 off frac |   5 V/div |
|      87 | CH1 off frac |   5 V/div |

A value of 0x80 means no correction, factor = 0.0
0x00 and 0xFF -> invalid, ignored (Factory setting is 0xFF)
Values >0x80 increase the offset, values <0x80 make it smaller.

|      Value | Offset |    Result |
|------------|--------|-----------|
|       0x00 |  0.000 | invalid   |
| 0x80 - 125 | -0.500 | smallest  |
|         .. |     .. | ..        |
|   0x80 - 1 | -0.002 | smaller   |
|       0x80 |  0.000 | no change |
|    0x80 +1 | +0.002 | taller    |
|         .. |     .. | ..        |
| 0x80 + 125 | +0.500 | tallest   |
|       0xFF |  0.000 | invalid   |

## Calibration

The calibration values can be determined and set with the program
[`calibrate_6022`](../examples/calibrate_6022.py)
(installed command, the wrapper `examples/calibrate_6022.py` behaves identically):

    usage: calibrate_6022 [-h] [-c] [-e] [-g]

    options:
      -h, --help           show this help message and exit
      -c, --create_config  create a config file
      -e, --eeprom         store calibration values in eeprom
      -g, --measure_gain   interactively measure gain (as well as offset)


## Pull Requests/Issues

If you have any extra information about this scope, open a pull request or issue and share your knowledge! I am very
open to any ideas or input from anyone interested.
