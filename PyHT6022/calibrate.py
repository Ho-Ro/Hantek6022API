#!/usr/bin/env python3
"""
Program to calibrate offset and gain of Hantek 6022BE/BL.

1. Measure offset at low and high speed for the four gain steps x10, x5, x2, x1
2. Measure gain for the four gain steps x10, x5, x2, x1
3. Write offset values into eeprom and config file

Configure with command line arguments:

    usage: calibrate.py [-h] [-c] [-e] [-g]

    optional arguments:
        -h, --help           show this help message and exit
        -c, --create_config  create config file
        -e, --eeprom         store calibration values in eeprom
        -g, --measure_gain   interactively measure gain (as well as offset)
"""

import sys
import time
import binascii
import argparse
from PyHT6022.LibUsbScope import Oscilloscope

# mV/div ranges
V_DIV = (20, 50, 100, 200, 500, 1000, 2000, 5000)
# corresponding amplifier gain settings
GAINS = (10, 10, 10, 5, 2, 1, 1, 1)
# available amplifier gains
GAIN_STEPS = (10, 5, 2, 1)


def read_avg(scope, voltage_range, sample_rate=110, repeat=1, samples=12 * 1024):
    """Average over 100ms @ 100kS/s -> 5 cycles @ 50 Hz or 6 cycles @ 60 Hz to cancel AC hum."""
    scope.set_sample_rate(sample_rate)
    scope.set_ch1_voltage_range(voltage_range)
    if sample_rate == 30:
        scope.set_num_channels(1)
    else:
        scope.set_num_channels(2)
        scope.set_ch2_voltage_range(voltage_range)

    time.sleep(0.1)

    sum1 = 0
    sum2 = 0
    count1 = 0
    count2 = 0

    for _ in range(repeat):  # repeat measurement
        ch1_data, ch2_data = scope.read_data(samples, raw=True, timeout=0)

        # skip first samples and keep 10000
        skip = samples - 10000

        for sample in ch1_data[skip:]:
            sum1 += sample
            count1 += 1
        if sample_rate != 30:
            for sample in ch2_data[skip:]:
                sum2 += sample
                count2 += 1

    # measured values are 0x80 binary offset -> 0V = 0x80
    avg1 = sum1 / count1 - 0x80
    if count2:
        avg2 = sum2 / count2 - 0x80
    else:
        avg2 = 0
    return (avg1, avg2)


def measure_offsets(scope):
    """Measure offset values for all gain steps."""
    offset1 = {}  # double offset at low speed
    offset2 = {}
    offlo1 = {}   # int offset at low speed
    offlo2 = {}
    offlo_1 = {}  # difference between double and int value
    offlo_2 = {}
    offhi1 = {}   # only ch1 for high speed
    offhi_1 = {}  # only ch1 for high speed

    for gain in GAIN_STEPS:
        # average 10 times over 100 ms (cancel 50 Hz / 60 Hz)
        print(f"Measure offset at low speed for gain {gain}")
        offset1[gain], offset2[gain] = read_avg(scope, gain, 110, 10)
        raw1 = int(round(offset1[gain]))
        fine1 = int(round((offset1[gain] - raw1) * 250.0))
        raw2 = int(round(offset2[gain]))
        fine2 = int(round((offset2[gain] - raw2) * 250.0))
        offlo1[gain] = raw1
        offlo_1[gain] = fine1
        offlo2[gain] = raw2
        offlo_2[gain] = fine2

        print(f"Measure offset at high speed for gain {gain}")
        off1, _ = read_avg(scope, gain, 30, 10)
        raw1 = int(round(off1))
        fine1 = int(round((off1 - raw1) * 250.0))
        offhi1[gain] = raw1
        offhi_1[gain] = fine1

    return offset1, offset2, offlo1, offlo2, offlo_1, offlo_2, offhi1, offhi_1


def create_config_file(scope, offset1, offset2, gain1=None, gain2=None):
    """Create calibration config file for OpenHantek."""
    product = scope.get_product_string()
    if product:
        cal_file = product + "_"
    else:
        cal_file = "DSO-6022BE_"
    serial_number = scope.get_serial_number_string()
    if serial_number:
        cal_file += serial_number + "_calibration.ini"
    else:
        cal_file += "_NN_calibration.ini"

    print(f"\nCalibration file: {cal_file}")
    config = open(cal_file, "w")
    config.write(f";OpenHantek calibration file: {cal_file}")
    config.write("\n;Created by tool 'calibrate_6022.py'\n\n")

    # offset as measured: values > 0 correct downwards, values < 0 correct upwards
    config.write("[offset]\n")
    for index, gain_id in enumerate(GAINS):
        volt_id = V_DIV[index]
        if abs(offset1[gain_id]) <= 25:   # offset too high -> skip
            config.write(f"ch0\\{volt_id}mV={offset1[gain_id]:6.2f}\n")
    for index, gain_id in enumerate(GAINS):
        volt_id = V_DIV[index]
        if abs(offset2[gain_id]) <= 25:   # offset too high -> skip
            config.write(f"ch1\\{volt_id}mV={offset2[gain_id]:6.2f}\n")

    config.write("\n[gain]\n")
    if gain1 and gain2:
        for index, gain_id in enumerate(GAINS):
            volt_id = V_DIV[index]
            g1 = gain1.get(gain_id)
            if g1:
                config.write(f"ch0\\{volt_id}mV={g1:6.4f}\n")
        for index, gain_id in enumerate(GAINS):
            volt_id = V_DIV[index]
            g2 = gain2.get(gain_id)
            if g2:
                config.write(f"ch1\\{volt_id}mV={g2:6.4f}\n")
    else:
        for index, gain_id in enumerate(GAINS):
            volt_id = V_DIV[index]
            config.write(f"ch0\\{volt_id}mV=1.0\n")
        for index, gain_id in enumerate(GAINS):
            volt_id = V_DIV[index]
            config.write(f"ch1\\{volt_id}mV=1.0\n")

    config.write("\n[eeprom]\nreplace_eeprom=true\n")
    config.close()


def measure_gains(scope, offset1, offset2):
    """Measure gain interactively."""
    print("\nCalculate gain adjustment")
    print("Apply the requested voltage (as exactly as possible) to both channels and press <ENTER>")
    print("You can also apply a slightly lower or higher stable voltage and type in this value\n")

    # theoretical gain error of 6022 front end due to nominal resistor values
    error = (1.00, 1.01, 0.99, 0.99)  # gainSteps 10x, 5x, 2x, 1x

    gain1 = {}
    gain2 = {}

    for idx, gain in enumerate(GAIN_STEPS):
        voltage = 4 / gain  # max input is slightly lower than 5V / gain
        setpoint = input(f"Apply {voltage:4.2f} V to both channels and press <ENTER> ")
        try:
            setpoint = float(setpoint)  # did the user supply an own voltage setting?
        except ValueError:
            setpoint = voltage  # else assume the proposed value 'voltage'

        # we expect value 'target'
        target = error[idx] * 100 * setpoint / voltage

        # get offset error for gain setting & channel
        off1 = offset1[gain]
        off2 = offset2[gain]

        # read raw values, average over 10 times 100 ms
        raw1, raw2 = read_avg(scope, gain, 110, 10)  # read @ 100kS/s

        # correct offset error
        value1 = raw1 - off1
        value2 = raw2 - off2

        if raw1 > 250 or value1 < 80 or value1 > 120:  # overdriven or out of range
            gain1[gain] = None  # ignore setting, no correction
        else:
            gain1[gain] = target / value1  # corrective gain factor

        if raw2 > 250 or value2 < 80 or value2 > 120:  # same as for 1st channel
            gain2[gain] = None
        else:
            gain2[gain] = target / value2

    return gain1, gain2


def update_eeprom_calibration(ee_calibration, offlo1, offlo2, offlo_1, offlo_2,
                              offhi1, offhi_1, gain1=None, gain2=None):
    """Update eeprom calibration data with measured values."""
    for index, gain_id in enumerate(GAINS):
        # store values in offset binary format (zero = 0x80, as in factory setup)
        if abs(offlo1[gain_id]) <= 25:  # offset too high -> skip
            ee_calibration[2 * index] = 0x80 + offlo1[gain_id]  # CH1 offset integer part
        if abs(offlo_1[gain_id]) <= 125:  # frac part not plausible
            ee_calibration[2 * index + 48] = 0x80 + offlo_1[gain_id]  # CH1 offset fractional part
        if abs(offlo2[gain_id]) <= 25:
            ee_calibration[2 * index + 1] = 0x80 + offlo2[gain_id]  # CH2 offset integer part
        if abs(offlo_2[gain_id]) <= 125:
            ee_calibration[2 * index + 49] = 0x80 + offlo_2[gain_id]  # CH2 offset fractional part
        if abs(offhi1[gain_id]) <= 25:
            ee_calibration[2 * index + 16] = 0x80 + offhi1[gain_id]  # same for CH2
        if abs(offhi_1[gain_id]) <= 125:
            ee_calibration[2 * index + 64] = 0x80 + offhi_1[gain_id]

    if gain1 and gain2:
        for index, gain_id in enumerate(GAINS):
            g1 = gain1.get(gain_id)
            g2 = gain2.get(gain_id)
            if g1:
                # convert double 0.75 ... 1.25 -> byte 0x80-125 ... 0x80+125
                ee_calibration[2 * index + 32] = int(round((g1 - 1) * 500 + 0x80))
            if g2:
                ee_calibration[2 * index + 33] = int(round((g2 - 1) * 500 + 0x80))

    return ee_calibration


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='calibrate_6022.py',
        description='Measure offset and gain calibration values'
    )
    parser.add_argument("-c", "--create_config", action="store_true",
                        help="create a config file")
    parser.add_argument("-e", "--eeprom", action="store_true",
                        help="store calibration values in eeprom")
    parser.add_argument("-g", "--measure_gain", action="store_true",
                        help="interactively measure gain (as well as offset)")
    return parser.parse_args()


def main():
    """Run the calibration routine."""
    args = parse_arguments()
    create_config = args.create_config
    eeprom = args.eeprom
    measure_gain = args.measure_gain

    print("Setting up scope...")

    scope = Oscilloscope()
    scope.setup()
    if not scope.open_handle():
        sys.exit(-1)

    if not scope.is_device_firmware_present:
        print('Upload firmware...')
        scope.flash_firmware()

    scope.supports_single_channel = True

    # select two channels
    scope.set_num_channels(2)
    # set coupling of both channels to DC
    scope.set_ch1_ch2_ac_dc(scope.DC_DC)

    # get calibration values stored in the scope
    ee_calibration = bytearray(scope.get_calibration_values(32 + 16 + 32))

    # measure offset
    print("\nCalculate zero adjustment")
    input("Apply 0 V to both channels and press <ENTER> ")

    offset1, offset2, offlo1, offlo2, offlo_1, offlo_2, offhi1, offhi_1 = measure_offsets(scope)

    gain1 = None
    gain2 = None

    if measure_gain:
        gain1, gain2 = measure_gains(scope, offset1, offset2)

    if create_config:
        create_config_file(scope, offset1, offset2, gain1, gain2)

    # update eeprom calibration data
    ee_calibration = update_eeprom_calibration(
        ee_calibration, offlo1, offlo2, offlo_1, offlo_2,
        offhi1, offhi_1, gain1, gain2
    )

    if eeprom:
        print("\nEEPROM content [  8 .. 39 ]: ", binascii.hexlify(ee_calibration[0:32]))
        print("EEPROM content [ 40 .. 55 ]: ", binascii.hexlify(ee_calibration[32:48]))
        print("EEPROM content [ 56 .. 87 ]: ", binascii.hexlify(ee_calibration[48:80]))
        # finally store the calibration values into eeprom
        scope.set_calibration_values(ee_calibration)

    scope.close_handle()


if __name__ == "__main__":
    main()
