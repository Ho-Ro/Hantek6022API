# Hantek6022API

[![Build_Check](https://github.com/Ho-Ro/Hantek6022API/actions/workflows/build_check.yml/badge.svg)](https://github.com/Ho-Ro/Hantek6022API/actions/workflows/build_check.yml)
[![Stability: Active](https://masterminds.github.io/stability/active.svg)](https://masterminds.github.io/stability/active.html)
[![CodeFactor](https://www.codefactor.io/repository/github/ho-ro/hantek6022api/badge)](https://www.codefactor.io/repository/github/Ho-Ro/Hantek6022API)
[![Downloads total](https://img.shields.io/github/downloads/Ho-Ro/Hantek6022API/total?color=blue)](https://github.com/Ho-Ro/Hantek6022API/releases)

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/Ho-Ro/Hantek6022API)](https://github.com/Ho-Ro/Hantek6022API/releases)
[![GitHub Release Date](https://img.shields.io/github/release-date/Ho-Ro/Hantek6022API?color=blue)](https://github.com/Ho-Ro/Hantek6022API/releases)
[![Downloads of latest release](https://img.shields.io/github/downloads/Ho-Ro/Hantek6022API/latest/total?color=blue)](https://github.com/Ho-Ro/Hantek6022API/releases/latest)
[![GitHub commits since latest release](https://img.shields.io/github/commits-since/Ho-Ro/Hantek6022API/latest?color=blue)](https://github.com/Ho-Ro/Hantek6022API/commits/main)

This repo is based on the excellent work of [Robert](https://github.com/rpcope1/Hantek6022API)
and [Jochen](https://github.com/jhoenicke/Hantek6022API) 
and focusses mainly on Hantek6022BE/BL under Linux (development system: Debian stable).

## Hantek 6022 Firmware

* __Hantek6022BE custom firmware is feature complete and usable for [OpenHantek6022](https://github.com/OpenHantek/OpenHantek6022)__

* __Hantek6022BL custom firmware is feature complete but not as intensively tested as the BE version__

## Hantek 6022 Python API for Linux

![Scope Visualisation Example](examples/plot_from_capture.png)

This is a API for Python3 for the ultra-cheap, reasonably usable (and hackable) 6022 DSO,
with a libusb implementation via libusb1 for Linux.

The scope can be accessed by instantiating an oscilloscope object.
Things like voltage divisions and sampling rates can be set by the appropriate methods.
Please check the provided [example programs](https://github.com/Ho-Ro/Hantek6022API/tree/main/examples),
the comments will give you more hints for own experiments.
Each method has documentation about what it is doing, and hopefully the variable names are clear enough
to give you an idea of what they are for.

## Linux Install

If you're on Linux, you're in luck.
Provided are bindings for libusb to operate this little device with simple python commands.
If you are a user, you can simply download the latest Debian package from
[releases](https://github.com/Ho-Ro/Hantek6022API/releases) and use the utilities in
[examples](https://github.com/Ho-Ro/Hantek6022API/tree/main/examples),
all tools named `*_6022.py` are copied to `/usr/bin` and are thus globally available.

If you're lucky you can even use the programs without installing anything.
You just need a working `python3` and the python modules `libusb1`, `matplotlib`, and `numpy`.
This can be achived on debian with `apt install python3-usb1 python3-matplotlib python3-numpy`,
or use `pip install libusb1 matplotlib numpy`.

All you need is the `PyHT6022` directory in the directory where your Python program is located
(e.g. in `examples`). This means:

- download this repo (as `https://github.com/Ho-Ro/Hantek6022API/archive/refs/heads/main.zip`)
- or execute `git clone https://github.com/Ho-Ro/Hantek6022API.git`
- to enable user access to the device copy (as root) the file `udev/60-hantek6022api.rules`
into `/etc/udev/rules.d`
- go to `examples`
- try e.g. `python3 get_serial_number.py`

## Developer Info

If you are a developer, you will definitely clone the repo and work with it more intensively. So please read on...

You may wish to first add `60-hantek-6022-usb.rules` (living in [udev](https://github.com/Ho-Ro/Hantek6022API/tree/main/udev))
to your udev rules, via

    sudo cp 60-hantek-6022-usb.rules /etc/udev/rules.d/

After you've done this, the scope should automatically come up with the correct permissions to be accessed
without being root user.

The following instructions are tested with Debian stable versions *stretch*, *buster*, *bullseye*, and *bookworm*
and are executed also automatically by GitHub under Ubuntu (*2204*) after each push to this repo - have a look
at the [GitHub Action](https://github.com/Ho-Ro/Hantek6022API/actions/workflows/build_check.yml).
On each successful run a Debian package is available under *Artifacts*.

### Build Preparations

To compile the custom firmware you have to install (as root) the *small devices c compiler* `sdcc` and the tool `pkgconf`:

    sudo apt install sdcc pkgconf

Take care when the SDCC version gets updated. the step from 3.9 to 4.0 introduced a nasty regression due to [less optimal code](https://github.com/Ho-Ro/Hantek6022API/blob/4cb4edbf1e6d2d5df21dbb4dabb8f51c932a0348/PyHT6022/Firmware/DSO6022BE/scope6022.inc#L80)
from the newer version.

Hantek6022API uses the submodule [fx2lib](https://github.com/Ho-Ro/fx2lib) that I cloned from the
[original fx2lib](https://github.com/djmuhlestein/fx2lib) to do minor maintenance updates.

Pull the submodule in (once):

    git submodule init
    git submodule update --remote

### Linux Build

To build the custom firmware run `make` in the top level directory:

    make

To build a simple debian package (this is the preferred installation procedure) you have to install some more .deb packages

    sudo apt install python3-setuptools python3-stdeb dh-python python3-libusb1 sdcc libusb-1.0 libusb-1.0-0-dev;

Create a debian package:

    make deb

that can be installed with

    make debinstall

which calls

    sudo dpkg -i `ls deb_dist/hantek6022api_*.deb | tail -1`

for the latest debian package. This installs the python modules together with some utility programs.
The installed programs can also be uninstalled cleanly with

    sudo dpkg -P hantek6022api

You can then look at the scope traces via `capture_6022.py -t 0.01 | plot_from_capture_6022.py`,
or write your own programs - look at the programs in `examples` as a start.

If you want to make low-level experiments with the python commands you should bootstrap the scope for use:
With the device plugged in, run `upload_6022_firmware.py` once.
The *user tools* `*_6022.py` do this automatically at start.

**Don't Panik!**
The firmware is uploaded into RAM and is lost after switching off the scope or disconnecting
the USB, so the device can never be *bricked*.

This simple program sets the calibration output frequency to 400 Hz
(you can use each even divison of 2 MHz between 32 Hz and 100 kHz).

```python
#!/usr/bin/python3

# get the python package
from PyHT6022.LibUsbScope import Oscilloscope

# create an Osclloscope object
scope = Oscilloscope()

# setup the scope
scope.setup()

# attach to the scope
scope.open_handle()

# upload firmware unless already uploaded
if (not scope.is_device_firmware_present):
    scope.flash_firmware()

# and now set the calibration frequency output to 400 Hz
scope.set_calibration_frequency( 400 )
```

## It may even work under Windows

[@justlep](https://github.com/justlep) wrote:
> here is what I did:

    install Python3
    get the required libusb-1.0.dll file:
    download the v1.0.23 zip from
    https://sourceforge.net/projects/libusb/files/libusb-1.0/libusb-1.0.23/
    extract libusb-1.0.dll from the zip file into {Python install dir}/
    (where python.exe sits)

    prepare Hantek6022API:
    git clone https://github.com/Ho-Ro/Hantek6022API
    cd Hantek6022API
    pip install .

You can also use the `libusb-1.0.dll` file from the
[libusb-1.0 version](https://github.com/OpenHantek/OpenHantek6022/blob/main/cmake/libusb-1.0.21-win.7z)
that is provided by [OpenHantek6022](https://github.com/OpenHantek/OpenHantek6022).
The `libusb-1.0.dll` file should be found in the PATH, e.g. it could be in the `python.exe` directory
or together with the example programs in the same directory.

YMMV, I checked it only with a bare-bones virtual Win7 install under Debian.

See also [Problems running calibration (#13)](https://github.com/Ho-Ro/Hantek6022API/issues/13)

OpenHantek provides a new function for [offset calibration](https://github.com/OpenHantek/OpenHantek6022#offset-calibration)
and stores the calibration values persistently as an ini file. This ini file provides also entries for (manual) gain correction.
So in most cases you do not need the python tools anymore, that were difficult to install for Windows users. The following
section is therefore targeted to Linux (and MacOS) users as well as Windows users with a working libusb python installation.

## Create calibration values for OpenHantek

<img alt="Uncalibrated scope data" width="50%" src="HT6022BE_uncalibrated.png">

As you can see in the trace above the scope has a quite big zero point error (the measured real signal
switches between 0.0 V and 2.0 V) - also the gain is defined by resistors with 5% tolerance
in the frontend - in best case by two resistors R27/17 & R31/21 in the chain (x1),
in worst case by four resistors R27/17 & R31/21 & R32/23 & R18/19/22 in the chain (x2, x5, x10).

-> https://github.com/Ho-Ro/Hantek6022API/blob/main/hardware/6022BE_Frontend_with_pinout.jpg 

In the end you can have a statistical gain tolerance of about 7%...10% -> RSS analysis
(root sum square, square all tolerances, sum them up und calculate the root of this sum)
gives an expected tolerance range:

- sqrt( 2 * (5%)² ) = 1.4 * 5% = 7% for gain step x1
- sqrt( 4 * (5%)² ) = 2 * 5% = 10% for all other gains

To reduce this effect OpenHantek uses individual correction values:
1. Offset and gain calibration are read from a calibration file
`~/.config/OpenHantek/DSO-6022BE_NNNNNNNNNNNN_calibration.ini` (Linux, Unix, macOS)
or `%APPDATA%\OpenHantek\DSO-6022BE_NNNNNNNNNNNN_calibration.ini` for Windows
(where NN... is the unique serial number of the scope).
2. If this file is not available offset and calibration will be read from eeprom.

Step 2 uses the factory offset calibration values in eeprom.
Out of the box only offset values are contained in eeprom,
the program `calibrate_6022.py` (installed in `/usr/bin`) allows to update these values
in case the offset has changed over time.

Program to calibrate offset and gain of Hantek 6022BE/BL
1. Measure offset at low and high speed for the four gain steps x10, x5, x2, x1
2. Measure gain for the four gain steps x10, x5, x2, x1
3. Write offset values into eeprom and config file

Configure with command line arguments:

    usage: calibrate_6022.py [-h] [-c] [-e] [-g]

    optional arguments:
        -h, --help           show this help message and exit
        -c, --create_config  create config file
        -e, --eeprom         store calibration values in eeprom
        -g, --measure_gain   interactively measure gain (as well as offset)

### Fast Offset Calibration

Apply 0 V to both inputs (e.g. connect both probes to the GND calibration connector) and execute:

    calibrate_6022.py -e

### Complete Offset and Gain Calibration

If is also possible to measure and create also gain calibration.
To calibrate gain you have to apply a well known voltage (setpoint)
and compare it with the actual value that is read by the scope:

    calibrate_6022.py -ceg

This program guides you through the process.
You have to apply several different voltages to both input,
the program measures and compares them against the expected gain settings:

1. Apply 0 V. The Program reads the raw channel values and calculates all offset values
2. Apply 0.4 V. The program measures the gain for range x10
3. Apply 0.8 V. The program measures the gain for range x5
4. Apply 2.0 V. The program measures the gain for range x2
5. Apply 4.0 V. The program measures the gain for range x1
6. The program option `-e` stores the calibration values in eeprom
7. The program option `-c` creates a config file `modelDSO6022.conf`

This (optional) config file can be copied into directory `~/.config/OpenHantek`.
On every startup OpenHantek reads this file and applies the calibratipon accordingly.
The config file has higher priority than the eeprom content.
It has also the advantage not to mess with the eeprom.

The calibration voltages do not have to correspond absolutely to the given value,
but the applied voltage should not be much higher than the proposed value and must be determined exactly -
e.g. by measuring it with a multimeter. Type in the real measured voltage at the prompt.
4 fresh AA batteries in a battery holder are a simple and reliable voltage source:

Requested Voltage | Applied Voltage  | Comment
------------------|------------------|--------
0.4 V             | ~0.3 V           | 2 x AA with 1/10 probe
0.8 V             | ~0.6 V           | 4 x AA with 1/10 probe
2.0 V             | ~1.5 V           | 1 x AA
4.0 V             | ~3.0 V or ~4.5 V | 2 or 3 x AA

[Read more about the eeprom content...](docs/README.md#eeprom)

## Use the device as a data logger

The program `capture_6022.py` (also in `/usr/bin/`) allows to capture both channels over a long time.

The 256 x downsampling option increases the SNR and effective resolution (8bit -> at least 12 bit)
and allows very long time recording. The program uses the offset and gain calibration from EEPROM.
It writes the captured data into stdout or an outfile and calculates DC, AC and RMS of the data.

```
usage: capture_6022.py [-h] [-d [DOWNSAMPLE]] [-g] [-o OUTFILE] [-r RATE] [-t TIME] [-x CH1] [-y CH2]

Capture data from both channels of Hantek6022

options:
  -h, --help            show this help message and exit
  -d [DOWNSAMPLE], --downsample [DOWNSAMPLE]
                        downsample 256 x DOWNSAMPLE
  -g, --german          use comma as decimal separator
  -o OUTFILE, --outfile OUTFILE
                        write the data into OUTFILE (default: stdout)
  -r RATE, --rate RATE  sample rate in kS/s (20, 32, 50, 64, 100, 128, 200, default: 20)
  -t TIME, --time TIME  capture time in seconds (default: 1.0)
  -x CH1, --ch1 CH1     gain of channel 1 (1, 2, 5, 10, default: 1)
  -y CH2, --ch2 CH2     gain of channel 2 (1, 2, 5, 10, default: 1)
```

The program `plot_from_capture_6022.py` takes the captured data (either from stdin
or from a file from command line argument) and presents them as seen on top of this page.

```
usage: plot_from_capture_6022.py [-h] [-i INFILE] [-c CHANNEL] [-s [MAX_FREQ]] [-x]

Plot output of capture_6022.py over time

options:
  -h, --help            show this help message and exit
  -i INFILE, --infile INFILE
                        read the data from INFILE (default: stdin)
  -c CHANNEL, --channel CHANNEL
                        show only CH1 or CH2, default: show both)
  -s [MAX_FREQ], --spectrum [MAX_FREQ]
                        display the spectrum of the samples, optional up to MAX_FREQ
  -x, --xkcd            plot in XKCD style :)
```

The program `fft_from_capture_6022.py` takes the captured data (either from stdin
or from a file from command line argument) and shows the spectrum.

```
usage: fft_from_capture_6022.py [-h] [-i INFILE] [-f | -n] [-x]

Plot FFT of output from capture_6022.py, use hann windowing as default

options:
  -h, --help            show this help message and exit
  -i INFILE, --infile INFILE
                        read the data from INFILE, (default: stdin)
  -f, --flat_top        use flat top window
  -n, --no_window       use no window
  -x, --xkcd            plot in XKCD style :)
```

![fft from capture](examples/fft_from_capture.png)

## Other neat things you can do

While this scope isn't quite as poweful as your many-thousand dollar Tektronix or even your run of the mill Rigol 1102E,
with a little bit of programming, it's capable of doing interesting things. User -johoe on reddit was able to use
[this library and scope to launch a successful side-channel attack on his TREZOR bitcoin device, and extract the
device's private keys](http://www.reddit.com/r/TREZOR/comments/31z7hc/extracting_the_private_key_from_a_trezor_with_a/#);
yes side-channel attacks aren't just for NSA spooks and crusty academics anymore, even you can do it in your home
with this inexpensive USB scope. :)

If you have you have your own examples or have seen this library used, please let me know so I can add the examples here.

## TODO

 1. Clean up library, apply good formatting.
 2. Clean up unit tests.
 3. Add more examples.

One excellent ultimate goal for this would to make it play nice with cheap ARM SBCs like the Raspberry Pi, such that
this could be used as a quick and dirty DAQ for many interesting systems.

For additional (interesting) details, the inquisitive reader should take two or three hours and read:
http://www.eevblog.com/forum/testgear/hantek-6022be-20mhz-usb-dso/ 

