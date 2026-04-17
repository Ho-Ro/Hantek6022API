#!/usr/bin/env python3
"""
Capture data from Hantek 6022BE/BL oscilloscope.

This module provides functionality to capture data from both channels
of a Hantek 6022BE/BL USB oscilloscope over a specified time period
with optional downsampling.
"""

import argparse
import sys
import time
import numpy as np
from PyHT6022.LibUsbScope import Oscilloscope


class HantekCapture:
    """Class to handle data capture from Hantek 6022 oscilloscope."""

    # Sample rate mapping (in kS/s)
    SAMPLE_RATES = {
        20: 0,   # 20 kS/s
        32: 1,   # 32 kS/s
        50: 2,   # 50 kS/s
        64: 3,   # 64 kS/s
        100: 4,  # 100 kS/s
        128: 5,  # 128 kS/s
        200: 6,  # 200 kS/s
    }

    # Gain mapping
    GAIN_VALUES = {
        1: 0,
        2: 1,
        5: 2,
        10: 3,
    }

    def __init__(self):
        """Initialize the oscilloscope connection."""
        self.scope = Oscilloscope()
        self.scope.setup()
        self.scope.open_handle()

        # Upload firmware if not already present
        if not self.scope.is_device_firmware_present:
            self.scope.flash_firmware()

    def set_sample_rate(self, rate_khz):
        """Set the sample rate for both channels.

        Args:
            rate_khz: Sample rate in kHz (20, 32, 50, 64, 100, 128, 200)
        """
        if rate_khz not in self.SAMPLE_RATES:
            raise ValueError(f"Invalid sample rate. Choose from: {list(self.SAMPLE_RATES.keys())}")

        rate_index = self.SAMPLE_RATES[rate_khz]
        self.scope.set_sample_rate(rate_index)
        return rate_khz

    def set_channel_gain(self, channel, gain):
        """Set gain for a specific channel.

        Args:
            channel: Channel number (1 or 2)
            gain: Gain value (1, 2, 5, 10)
        """
        if gain not in self.GAIN_VALUES:
            raise ValueError(f"Invalid gain. Choose from: {list(self.GAIN_VALUES.keys())}")

        gain_index = self.GAIN_VALUES[gain]
        if channel == 1:
            self.scope.set_ch1_voltage_range(gain_index)
        elif channel == 2:
            self.scope.set_ch2_voltage_range(gain_index)
        else:
            raise ValueError("Channel must be 1 or 2")

    def capture_data(self, duration, downsample=1):
        """Capture data for specified duration.

        Args:
            duration: Capture duration in seconds
            downsample: Downsampling factor (1, 2, 4, 8, 16, 32, 64, 128, 256)

        Returns:
            Tuple of (ch1_data, ch2_data, actual_sample_rate)
        """
        # Calculate number of samples needed
        sample_rate = self.scope.get_sample_rate() * 1000  # Convert to samples/second
        samples_needed = int(duration * sample_rate)

        # Apply downsampling if requested
        if downsample > 1:
            samples_needed = samples_needed // downsample
            self.scope.set_down_sampling(downsample)

        # Prepare data arrays
        ch1_data = np.zeros(samples_needed, dtype=np.float32)
        ch2_data = np.zeros(samples_needed, dtype=np.float32)

        # Capture data in chunks
        chunk_size = 1024  # Adjust based on device capabilities
        samples_captured = 0

        self.scope.start_capture()

        while samples_captured < samples_needed:
            remaining = samples_needed - samples_captured
            current_chunk = min(chunk_size, remaining)

            # Read data from scope
            ch1_chunk, ch2_chunk = self.scope.read_data(current_chunk)

            if len(ch1_chunk) > 0:
                end_idx = samples_captured + len(ch1_chunk)
                ch1_data[samples_captured:end_idx] = ch1_chunk
                ch2_data[samples_captured:end_idx] = ch2_chunk
                samples_captured += len(ch1_chunk)
            else:
                # No data available, wait a bit
                time.sleep(0.001)

        self.scope.stop_capture()

        # Calculate actual sample rate
        actual_rate = sample_rate / downsample if downsample > 1 else sample_rate

        return ch1_data, ch2_data, actual_rate

    def calculate_statistics(self, data):
        """Calculate statistics for captured data.

        Args:
            data: numpy array of captured values

        Returns:
            Dictionary with DC, AC, and RMS values
        """
        if len(data) == 0:
            return {'dc': 0.0, 'ac': 0.0, 'rms': 0.0}

        dc = np.mean(data)
        ac = np.std(data)
        rms = np.sqrt(np.mean(data**2))

        return {
            'dc': dc,
            'ac': ac,
            'rms': rms,
            'min': np.min(data),
            'max': np.max(data),
            'peak_to_peak': np.max(data) - np.min(data)
        }

    def format_value(self, value, use_german_format=False):
        """Format a numeric value with appropriate decimal separator.

        Args:
            value: Numeric value to format
            use_german_format: If True, use comma as decimal separator

        Returns:
            Formatted string
        """
        if use_german_format:
            return f"{value:.6f}".replace('.', ',')
        else:
            return f"{value:.6f}"

    def close(self):
        """Close the oscilloscope connection."""
        if self.scope:
            self.scope.close_handle()


def write_output_header(outfile, args, use_german_format=False):
    """Write header information to output file.

    Args:
        outfile: File object to write to
        args: Command line arguments
        use_german_format: Use comma as decimal separator
    """
    outfile.write("# Hantek 6022 Capture Data\n")
    outfile.write(f"# Sample Rate: {args.rate} kS/s\n")
    outfile.write(f"# Capture Time: {args.time} seconds\n")
    outfile.write(f"# Channel 1 Gain: x{args.ch1}\n")
    outfile.write(f"# Channel 2 Gain: x{args.ch2}\n")
    if args.downsample:
        outfile.write(f"# Downsample Factor: {args.downsample}\n")
    outfile.write("# Format: Time(s), CH1(V), CH2(V)\n")

    if use_german_format:
        outfile.write("# Dezimaltrennzeichen: Komma\n")


def write_statistics(outfile, ch1_stats, ch2_stats, use_german_format=False):
    """Write statistics to output as comments.

    Args:
        outfile: File object to write to
        ch1_stats: Statistics dictionary for channel 1
        ch2_stats: Statistics dictionary for channel 2
        use_german_format: Use comma as decimal separator
    """
    dec = ',' if use_german_format else '.'

    outfile.write("#\n# Statistics:\n")
    outfile.write(f"# CH1 - DC: {ch1_stats['dc']:.6f}{dec} AC: {ch1_stats['ac']:.6f}{dec} RMS: {ch1_stats['rms']:.6f}\n".replace('.', dec))
    outfile.write(f"# CH1 - Min: {ch1_stats['min']:.6f}{dec} Max: {ch1_stats['max']:.6f}{dec} P-P: {ch1_stats['peak_to_peak']:.6f}\n".replace('.', dec))
    outfile.write(f"# CH2 - DC: {ch2_stats['dc']:.6f}{dec} AC: {ch2_stats['ac']:.6f}{dec} RMS: {ch2_stats['rms']:.6f}\n".replace('.', dec))
    outfile.write(f"# CH2 - Min: {ch2_stats['min']:.6f}{dec} Max: {ch2_stats['max']:.6f}{dec} P-P: {ch2_stats['peak_to_peak']:.6f}\n".replace('.', dec))


def capture_main(args=None):
    """Main function for command-line interface.

    Args:
        args: Command line arguments (if None, parse from sys.argv)
    """
    parser = argparse.ArgumentParser(
        description='Capture data from both channels of Hantek6022',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('-d', '--downsample',
                       type=int,
                       nargs='?',
                       const=256,
                       help='downsample 256 x DOWNSAMPLE')

    parser.add_argument('-g', '--german',
                       action='store_true',
                       help='use comma as decimal separator')

    parser.add_argument('-o', '--outfile',
                       type=str,
                       help='write the data into OUTFILE (default: stdout)')

    parser.add_argument('-r', '--rate',
                       type=int,
                       default=20,
                       choices=[20, 32, 50, 64, 100, 128, 200],
                       help='sample rate in kS/s (default: 20)')

    parser.add_argument('-t', '--time',
                       type=float,
                       default=1.0,
                       help='capture time in seconds (default: 1.0)')

    parser.add_argument('-x', '--ch1',
                       type=int,
                       default=1,
                       choices=[1, 2, 5, 10],
                       help='gain of channel 1 (default: 1)')

    parser.add_argument('-y', '--ch2',
                       type=int,
                       default=1,
                       choices=[1, 2, 5, 10],
                       help='gain of channel 2 (default: 1)')

    args = parser.parse_args(args)

    # Initialize capture
    capture = HantekCapture()

    try:
        # Configure scope
        capture.set_sample_rate(args.rate)
        capture.set_channel_gain(1, args.ch1)
        capture.set_channel_gain(2, args.ch2)

        # Capture data
        downsample_factor = args.downsample if args.downsample else 1
        ch1_data, ch2_data, actual_rate = capture.capture_data(args.time, downsample_factor)

        # Calculate statistics
        ch1_stats = capture.calculate_statistics(ch1_data)
        ch2_stats = capture.calculate_statistics(ch2_data)

        # Prepare output
        if args.outfile:
            outfile = open(args.outfile, 'w')
        else:
            outfile = sys.stdout

        try:
            # Write header
            write_output_header(outfile, args, args.german)

            # Write statistics as comments
            write_statistics(outfile, ch1_stats, ch2_stats, args.german)
            outfile.write("#\n")

            # Write data
            time_step = 1.0 / actual_rate
            dec = ',' if args.german else '.'

            for i in range(len(ch1_data)):
                time_val = i * time_step
                time_str = f"{time_val:.6f}".replace('.', dec)
                ch1_str = f"{ch1_data[i]:.6f}".replace('.', dec)
                ch2_str = f"{ch2_data[i]:.6f}".replace('.', dec)
                outfile.write(f"{time_str}\t{ch1_str}\t{ch2_str}\n")

        finally:
            if args.outfile:
                outfile.close()

        # Print summary to stderr
        sys.stderr.write(f"Capture complete:\n")
        sys.stderr.write(f"  Samples captured: {len(ch1_data)}\n")
        sys.stderr.write(f"  Duration: {args.time:.3f} seconds\n")
        sys.stderr.write(f"  Actual sample rate: {actual_rate:.1f} S/s\n")
        sys.stderr.write(f"  CH1 - DC: {ch1_stats['dc']:.4f}V, AC: {ch1_stats['ac']:.4f}V, RMS: {ch1_stats['rms']:.4f}V\n")
        sys.stderr.write(f"  CH2 - DC: {ch2_stats['dc']:.4f}V, AC: {ch2_stats['ac']:.4f}V, RMS: {ch2_stats['rms']:.4f}V\n")

    finally:
        capture.close()


def main():
    """Entry point for console script."""
    capture_main()


if __name__ == "__main__":
    main()
