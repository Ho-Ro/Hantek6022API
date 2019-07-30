/*
 * This file is part of the sigrok-firmware-fx2lafw project.
 *
 * Copyright (C) 2009 Ubixum, Inc.
 * Copyright (C) 2015 Jochen Hoenicke
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#include <fx2macros.h>
#include <fx2ints.h>
#include <autovector.h>
#include <delay.h>
#include <setupdat.h>
#include <i2c.h>
#include <eputils.h>

#define SET_ANALOG_MODE()

#define SET_COUPLING(x)

#define SET_CALIBRATION_PULSE(x)

#define TOGGLE_CALIBRATION_PIN() do { PA7 = !PA7; } while (0)

#define LED_CLEAR() do { PC0 = 1; PC1 = 1; } while (0)
#define LED_GREEN() do { PC0 = 1; PC1 = 0; } while (0)
#define LED_RED()   do { PC0 = 0; PC1 = 1; } while (0)
#define LED_RED_TOGGLE() do { PC0 = !PC0; PC1 = 1; } while (0)

/* CTLx pin index (IFCLK, ADC clock input). */
#define CTL_BIT 2

#define OUT0 ((1 << CTL_BIT) << 4) /* OEx = 1, CTLx = 0 */

#if 0

// struct samplerate_info{ rate, wait0, wait1, opc0, opc1, out0, ifcfg };
// rate -> ID 
// wait0, wait1, opc0, opc1, out0 -> GPIF waveform registers
// ifcfg -> IFCONFIG register (TRM 15.5.2)
//
// IFCONFIG.7 : IFCLKSRC, 0: ext, 1: int (30/48 MHz)
// IFCONFIG.6 : 3048MHZ, 0: 30MHz, 1: 48MHz
// IFCONFIG.5 : IFCLKOE, 0: tri-state, 1: drive
// IFCONFIG.4 : IFCLKPOL, 0: normal polarity, 1: inverted
// IFCONFIG.3 : ASYNC, 0: synchronously, clock supplied to IFCLK pin, 1: asynchronously, FIFO provides r/w strobes
// IFCONFIG.2 : GSTATE, 1: PE.[10] = GSTATE.[10]
// IFCONFIG.[10] : 00: ports, 01: reserved, 10: GPIF (internal) master, 11: slave FIFO (external master)
//

#define IFCLK48 0xca
#define IFCLK30 0x8a

#if 1
static const struct samplerate_info samplerates[] = {
	{  48, 0x80,   0, 3, 0, 0x00, 0xea },
	{  30, 0x80,   0, 3, 0, 0x00, 0xaa },
	{  24,    1,   0, 2, 1, OUT0, IFCLK48 },
	{  15,    1,   0, 2, 1, OUT0, IFCLK30 },
	{  12,    2,   1, 2, 0, OUT0, IFCLK48 },
	{  10,    1,   1, 2, 0, OUT0, IFCLK30 },
	{   5,    3,   2, 2, 0, OUT0, IFCLK30 },
	{   2,    8,   7, 2, 0, OUT0, IFCLK30 },
	{   1,   15,  14, 2, 0, OUT0, IFCLK30 },
	{ 150,   30,  29, 2, 0, OUT0, IFCLK30 },
	{ 120,  100,  99, 2, 0, OUT0, IFCLK30 },
	{ 110,  150, 149, 2, 0, OUT0, IFCLK30 },
	{ 106,  250, 249, 2, 0, OUT0, IFCLK30 }
};
#else
static const struct samplerate_info samplerates[] = {
	{  48, 0x80,   0, 3, 0, 0x00, 0xea },
	{  30, 0x80,   0, 3, 0, 0x00, 0xaa },
	{  24,    1,   0, 2, 1, OUT0, 0xca },
	{  16,    1,   1, 2, 0, OUT0, 0xca },
	{  12,    2,   1, 2, 0, OUT0, 0xca },
	{   8,    3,   2, 2, 0, OUT0, 0xca },
	{   4,    6,   5, 2, 0, OUT0, 0xca },
	{   2,   12,  11, 2, 0, OUT0, 0xca },
	{   1,   24,  23, 2, 0, OUT0, 0xca },
	{  50,   48,  47, 2, 0, OUT0, 0xca },
	{  20,  120, 119, 2, 0, OUT0, 0xca },
	{  10,  240, 239, 2, 0, OUT0, 0xca }
};
#endif
#endif

/*
 * This sets three bits for each channel, one channel at a time.
 * For channel 0 we want to set bits 2, 3 & 4 ( ...XXX.. => mask 0x1c )
 * For channel 1 we want to set bits 5, 6 & 7 ( XXX..... => mask 0xe0 )
 *
 * We convert the input values that are strange due to original
 * firmware code into the value of the three bits as follows:
 *
 * val -> bits
 * 1  -> 010b
 * 2  -> 001b
 * 5  -> 000b
 * 10 -> 011b
 *
 * The third bit is always zero since there are only four outputs connected
 * in the serial selector chip.
 *
 * The multiplication of the converted value by 0x24 sets the relevant bits in
 * both channels and then we mask it out to only affect the channel currently
 * requested.
 */
static BOOL set_voltage(BYTE channel, BYTE val)
{
	BYTE bits, mask;

	switch (val) {
	case 1:
		bits = 0x24 * 2;
		break;
	case 2:
		bits = 0x24 * 1;
		break;
	case 5:
		bits = 0x24 * 0;
		break;
	case 10:
		bits = 0x24 * 3;
		break;
	default:
		return FALSE;
	}

	mask = (channel) ? 0xe0 : 0x1c;
	IOC = (IOC & ~mask) | (bits & mask);

	return TRUE;
}

#include "scope6022.inc"
