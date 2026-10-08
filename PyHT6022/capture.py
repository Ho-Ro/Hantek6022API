#!/usr/bin/env python3
"""
Capture data from Hantek 6022BE/BL oscilloscope.

Samples both channels over a defined time and writes the time stamp and the
voltage values as CSV data to stdout or to a file:

    time[s], ch1[V], ch2[V]

The offset and gain calibration values from the EEPROM are applied, the
resulting values are in volts. With '-d' the samples are averaged over
blocks of 256 samples (increases SNR and effective resolution), with
'-d DOWNSAMPLE' over DOWNSAMPLE such blocks. DC, AC and RMS of the
captured data are printed to stderr.

usage: capture_6022 [-h] [-d [DOWNSAMPLE]] [-g] [-o OUTFILE] [-r RATE]
                    [-t TIME] [-x CH1] [-y CH2]
"""

import argparse
import math
import sys
import time

from PyHT6022.LibUsbScope import Oscilloscope

# valid sample rates in kS/s
VALID_SAMPLE_RATES = (20, 32, 50, 64, 100, 128, 200)
# valid gain (voltage range) settings
VALID_GAINS = (1, 2, 5, 10)
# samples per channel of one bulk transfer block (bulk interface, 512 byte packets)
BLOCK_SIZE = 256
# transfers sent to the kernel at the same time, the higher the more gapless
OUTSTANDING_TRANSFERS = 10


def sample_rate_id(sample_rate):
    """Convert a sample rate in S/s into the rate index expected by the firmware."""
    if sample_rate < 1e6:
        return int(round(100 + sample_rate / 10e3))  # 20k..500k -> 102..150
    return int(round(sample_rate / 1e6))             # 1M..48M -> 1..48


def build_arg_parser():
    """Construct the argument parser for the capture_6022 command."""
    rate_help = "sample rate in kS/s ("
    for valid_rate in VALID_SAMPLE_RATES:
        rate_help += str(valid_rate) + ", "
    rate_help += "default: 20)"

    parser = argparse.ArgumentParser(
        description='Capture data from both channels of Hantek6022'
    )
    parser.add_argument(
        '-d', '--downsample',
        action='store',
        type=int,
        default=0,
        const=1,
        nargs='?',
        help='downsample 256 x DOWNSAMPLE'
    )
    parser.add_argument(
        '-g', '--german',
        action='store_true',
        help='use comma as decimal separator'
    )
    parser.add_argument(
        '-o', '--outfile',
        type=argparse.FileType('w'),
        help='write the data into OUTFILE (default: stdout)'
    )
    parser.add_argument(
        '-r', '--rate',
        type=int,
        default=20,
        help=rate_help
    )
    parser.add_argument(
        '-t', '--time',
        type=float,
        default=1,
        help='capture time in seconds (default: 1.0)'
    )
    parser.add_argument(
        '-x', '--ch1',
        type=int,
        default=1,
        help='gain of channel 1 (1, 2, 5, 10, default: 1)'
    )
    parser.add_argument(
        '-y', '--ch2',
        type=int,
        default=1,
        help='gain of channel 2 (1, 2, 5, 10, default: 1)'
    )
    return parser


class SampleWriter:
    """
    Callback for Oscilloscope.read_async().

    Scales the raw ADC samples into volts with the EEPROM calibration values,
    optionally averages them over blocks, writes them to the output file and
    accumulates the DC and RMS sums for the final statistics.
    """

    def __init__(self, scope, ch1_gain, ch2_gain, sample_rate, sample_time,
                 downsample, outfile, german):
        """
        :param scope: The Oscilloscope object (used for scaling the samples).
        :param ch1_gain: Gain (voltage range) setting of channel 1.
        :param ch2_gain: Gain (voltage range) setting of channel 2.
        :param sample_rate: The sample rate in S/s.
        :param sample_time: Requested capture time in seconds.
        :param downsample: Averaging factor, 0 or 1 = no downsampling.
        :param outfile: Open file object that receives the CSV data.
        :param german: Use comma as decimal separator.
        """
        self.scope = scope
        self.ch1_gain = ch1_gain
        self.ch2_gain = ch2_gain
        self.sample_time = sample_time
        self.downsample = downsample
        self.outfile = outfile
        self.german = german
        self.tick = 1.0 / sample_rate
        self.skip_first = True  # skip the 1st (unstable) block
        self.total_size = 0
        self.points = 0  # data points written to the output file
        self.dc1 = 0.0
        self.dc2 = 0.0
        self.rms1 = 0.0
        self.rms2 = 0.0
        self.avg1 = 0.0  # pending block averages for downsampling
        self.avg2 = 0.0
        self.slowdown = 0  # collected blocks for the current average
        self.timestep = 0.0

    def __call__(self, ch1_data, ch2_data):
        """Handle one data block delivered by the asynchronous reader."""
        size = len(ch1_data)
        if size == 0:
            return
        if self.skip_first:  # skip the 1st (unstable) block
            self.skip_first = False
            return
        self.total_size += size
        ch1_scaled = self.scope.scale_read_data(ch1_data, self.ch1_gain, channel=1)
        ch2_scaled = self.scope.scale_read_data(ch2_data, self.ch2_gain, channel=2)

        # average over the block, prepare AC/DC
        av1 = 0.0
        for value in ch1_scaled:
            av1 += value
            self.dc1 += value
            self.rms1 += value * value
        av1 /= size
        av2 = 0.0
        for value in ch2_scaled:
            av2 += value
            self.dc2 += value
            self.rms2 += value * value
        av2 /= size

        if self.downsample:  # average further over several blocks
            self.avg1 += av1
            self.avg2 += av2
            self.slowdown += 1
            if self.slowdown >= self.downsample:
                self.slowdown = 0
                self.avg1 /= self.downsample
                self.avg2 /= self.downsample
                if self.timestep < self.sample_time:
                    self.write_line(self.timestep, self.avg1, self.avg2)
                self.avg1 = 0.0
                self.avg2 = 0.0
                self.timestep += self.tick * size * self.downsample
        else:  # write out every sample
            for value1, value2 in zip(ch1_scaled, ch2_scaled):
                if self.timestep < self.sample_time:
                    self.write_line(self.timestep, value1, value2)
                self.timestep += self.tick

    def write_line(self, time_value, value1, value2):
        """Write one CSV line, with german decimal comma if requested."""
        line = f"{time_value:>10.6f}, {value1:>10.5f}, {value2:>10.5f}\n"
        if self.german:
            line = line.replace(',', ';').replace('.', ',')
        self.outfile.write(line)
        self.points += 1

    def statistics(self):
        """
        Calculate the DC, AC and RMS values of the captured data.
        :return: dict with 'ch1' and 'ch2' entries, None if no samples were captured.
        """
        if self.total_size == 0:
            return None
        stats = {}
        for channel, dc, mean_square in (('ch1', self.dc1, self.rms1),
                                         ('ch2', self.dc2, self.rms2)):
            dc /= self.total_size
            mean_square /= self.total_size
            stats[channel] = {
                'dc': dc,
                'ac': math.sqrt(max(mean_square - dc * dc, 0.0)),
                'rms': math.sqrt(mean_square),
            }
        return stats


def write_summary(writer, options, effective_rate):
    """Print capture and statistics information to stderr."""
    plural = '' if writer.points == 1 else 's'
    line = (f"\rCaptured {writer.points} sample{plural} during "
            f"{options.time} second(s) @ {effective_rate} S/s")
    if writer.downsample:
        line += f" (downsampled {BLOCK_SIZE * writer.downsample}x)"
    line += "\n"
    if options.german:
        line = line.replace(',', ';').replace('.', ',')
    sys.stderr.write(line)

    stats = writer.statistics()
    if not stats:
        sys.stderr.write("no samples captured\n")
        return
    for channel, name in (('ch1', 'CH1'), ('ch2', 'CH2')):
        value = stats[channel]
        line = (f"{name}: DC = {value['dc']:8.4f} V, "
                f"AC = {value['ac']:8.4f} V, RMS = {value['rms']:8.4f} V\n")
        if options.german:
            line = line.replace(',', ';').replace('.', ',')
        sys.stderr.write(line)


def main(args=None):
    """
    Capture command entry point.
    :param args: Command line arguments, default: sys.argv.
    :return: Exit status.
    """
    parser = build_arg_parser()
    options = parser.parse_args(args)

    if options.rate not in VALID_SAMPLE_RATES:
        parser.error(f"samplerate must be one of: {VALID_SAMPLE_RATES}")
    if options.ch1 not in VALID_GAINS:
        parser.error(f"ch1 gain must be one of: {VALID_GAINS}")
    if options.ch2 not in VALID_GAINS:
        parser.error(f"ch2 gain must be one of: {VALID_GAINS}")

    sample_rate = options.rate * 1000  # kS/s -> S/s
    downsample = options.downsample

    scope = Oscilloscope()
    if not scope.open_handle():
        sys.stderr.write('scope open error - no device?\n')
        return 1

    # upload the firmware into the RAM of the device if not present
    if not scope.is_device_firmware_present:
        sys.stderr.write('Upload firmware...\n')
        scope.flash_firmware()

    # use the offset and gain calibration values stored in the EEPROM
    scope.get_calibration_values()
    # interface 0 = bulk transfer, >0 = isochronous transfer
    scope.set_interface(0)
    scope.set_num_channels(2)

    # calculate and set the sample rate ID from the real sample rate value
    scope.set_sample_rate(sample_rate_id(sample_rate))
    # set the gain for CH1 and CH2
    scope.set_ch1_voltage_range(options.ch1)
    scope.set_ch2_voltage_range(options.ch2)

    outfile = options.outfile or sys.stdout
    writer = SampleWriter(scope, options.ch1, options.ch2, sample_rate,
                          options.time, downsample, outfile, options.german)
    # correct the start time for the 1st (skipped) block
    start_time = time.time() + scope.packetsize / sample_rate

    try:
        # GO!
        scope.start_capture()
        shutdown_event = scope.read_async(writer, scope.packetsize,
                                          outstanding_transfers=OUTSTANDING_TRANSFERS,
                                          raw=True)

        # sample until the time is over, show the progress
        lastsec = None
        block_time = BLOCK_SIZE / sample_rate
        while True:
            to_go = start_time + options.time - time.time()
            if to_go <= -downsample * block_time:
                break
            if int(to_go) != lastsec:
                if lastsec is None:
                    sys.stderr.write(f"\rCapturing {options.time} seconds ...    ")
                elif lastsec > 0:
                    sys.stderr.write(f"\rCapturing {lastsec} seconds ...    ")
                else:
                    sys.stderr.write("\rCapturing ...              ")
                lastsec = int(to_go)
                outfile.flush()
            scope.poll()

        # STOP!
        scope.stop_capture()
        shutdown_event.set()
        # fetch remaining packets before closing the scope (max 1024 * 50us = 0.0512 s)
        time.sleep(0.1)
    finally:
        scope.close_handle()

    # calculate the effective sample rate
    effective_rate = sample_rate
    if downsample:
        effective_rate = sample_rate / BLOCK_SIZE / downsample
    write_summary(writer, options, effective_rate)

    if options.outfile:
        outfile.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
