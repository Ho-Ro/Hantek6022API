/*
 * This file is taken from the sigrok-firmware-fx2lafw project.
 *
 * Copyright (C) 2009 Ubixum, Inc.
 * Copyright (C) 2015 Jochen Hoenicke
 * Copyright (C) 2019-2024 Martin Homuth-Rosemann
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


// CLK_12M; CLK_24M; CLK_48M
#define CPU_FREQ CLK_48M

// 12 MHz: 500; 24 MHz: 1000; 48 MHz: 2000
#define TIMER2_VAL 2000

// CLK_48M & IFCLK30 -> 4 delays
#define SYNCDELAY SYNCDELAY4


static BOOL set_voltage( BYTE channel, BYTE val );

static BOOL set_coupling( BYTE val );

/* Change to support as many interfaces as you need. */
static BYTE altiface = 0;
static BYTE samplerate = 0;
static BYTE numchannels = 2;
static BYTE fifocfg = 0;

static volatile WORD ledinit = 500;
static volatile WORD ledcounter = 500;

static volatile __bit dosud = FALSE;
static volatile __bit dosuspend = FALSE;

extern __code BYTE highspd_dscr;
extern __code BYTE fullspd_dscr;


void resume_isr( void ) __interrupt (RESUME_ISR) { CLEAR_RESUME(); }


void sudav_isr( void ) __interrupt (SUDAV_ISR) {
    dosud = TRUE;
    CLEAR_SUDAV();
}


void usbreset_isr( void ) __interrupt (USBRESET_ISR) {
    handle_hispeed( FALSE );
    CLEAR_USBRESET();
}


void hispeed_isr( void ) __interrupt (HISPEED_ISR) {
    handle_hispeed( TRUE );
    CLEAR_HISPEED();
}


void suspend_isr( void ) __interrupt (SUSPEND_ISR) {
    dosuspend = TRUE;
    CLEAR_SUSPEND();
}


void timer2_isr( void ) __interrupt (TF2_ISR) {
    /* Toggle the probe calibration pin. */
    TOGGLE_CALIBRATION_PIN();
#ifdef LED_RED_TOGGLE
    // Avoid nasty sdcc 4.0 REGRESSION:
    // Do not use "if ( ledcounter && --ledcounter == 0 )"
    // Write separate statements!
    // Otherwise the ISR uses registers for reload -> additional push/pop ...
    // ... more cycles, fails for 100 kHz
    if ( ledcounter ) {
        --ledcounter;
        if ( ledcounter == 0 ) {  // led timed out?
            ledcounter = ledinit; // reload
            LED_RED_TOGGLE();
        }
    }
#endif
    TF2 = 0;
}


static void set_aadj() {
    if ( samplerate >= 24000 / numchannels ) {
        EP2ISOINPKTS &= 0x7f;
    } else {
        EP2ISOINPKTS |= 0x80;
    }
}


static BOOL set_numchannels( BYTE num ) {
    numchannels = num;
    if ( numchannels == 1 || numchannels == 2 ) {
        fifocfg = 7 + numchannels;
        EP2FIFOCFG = fifocfg;
        EP6FIFOCFG = fifocfg;
        set_aadj();
        return TRUE;
    }
    return FALSE;
}


static void clear_fifo( void ) {
    GPIFABORT = 0xff;
    SYNCDELAY;
    while ( !( GPIFTRIG & 0x80 ) )
        ;
    FIFORESET = 0x80;
    SYNCDELAY;
    EP2FIFOCFG = 0;
    SYNCDELAY;
    EP6FIFOCFG = 0;
    SYNCDELAY;
    FIFORESET = 0x02;
    SYNCDELAY;
    FIFORESET = 0x06;
    SYNCDELAY;
    EP2FIFOCFG = fifocfg;
    SYNCDELAY;
    EP6FIFOCFG = fifocfg;
    SYNCDELAY;
    FIFORESET = 0;
}


static void stop_sampling( void ) {
    GPIFABORT = 0xff;
    SYNCDELAY;
    INPKTEND = ( altiface == 0 ) ? 6 : 2;
}


static void start_sampling( void ) {
    int i;

    SET_ANALOG_MODE();

    clear_fifo();

    for ( i = 0; i < 1000; i++ )
        ;

    while ( !( GPIFTRIG & 0x80 ) )
        ;

    SYNCDELAY;
    GPIFTCB1 = 0x28;
    SYNCDELAY;
    GPIFTCB0 = 0;
    GPIFTRIG = ( altiface == 0 ) ? 6 : 4;
}


static void select_interface( BYTE alt ) {
    const BYTE *pPacketSize = ( ( USBCS & bmHSM ) ? &highspd_dscr : &fullspd_dscr ) + ( 9 + 9 + 4 + alt * ( 9 + 7 ) );

    altiface = alt;

    if ( alt == 0 ) {
        /* Bulk on EP6. */
        EP2CFG = 0x00;
        EP6CFG = 0xe0;
        EP6GPIFFLGSEL = 1;
        EP6AUTOINLENL = pPacketSize[ 0 ];
        EP6AUTOINLENH = pPacketSize[ 1 ];
    } else {
        /* Iso on EP2. */
        EP2CFG = 0xd8;
        EP6CFG = 0x00;
        EP2GPIFFLGSEL = 1;
        EP2AUTOINLENL = pPacketSize[ 0 ];
        EP2AUTOINLENH = pPacketSize[ 1 ] & 0x7;
        EP2ISOINPKTS = ( pPacketSize[ 1 ] >> 3 ) + 1;
        set_aadj();
    }
}


#include "waveforms.inc"

struct samplerate_info {
    const BYTE rate;
    const BYTE *waveform;
    const BYTE ifconfig;
};

static const struct samplerate_info samplerates[] = {
    // ID, waveform[32], ifconfig
    { 48, waveform_48, ifconfig_48 },    //  48 MS/s
    { 30, waveform_30, ifconfig_30 },    //  30 MS/s
    { 24, waveform_24, ifconfig_24 },    //  24 MS/s
    { 16, waveform_16, ifconfig_16 },    //  16 MS/s
    { 15, waveform_15, ifconfig_15 },    //  15 MS/s
    { 12, waveform_12, ifconfig_12 },    //  12 MS/s
    { 10, waveform_10, ifconfig_10 },    //  10 MS/s
    { 8, waveform_8, ifconfig_8 },       //   8 MS/s
    { 6, waveform_6, ifconfig_6 },       //   6 MS/s
    { 5, waveform_5, ifconfig_5 },       //   5 MS/s
    { 4, waveform_4, ifconfig_4 },       //   4 MS/s
    { 3, waveform_3, ifconfig_3 },       //   3 MS/s
    { 2, waveform_2, ifconfig_2 },       //   2 MS/s
    { 1, waveform_1, ifconfig_1 },       //   1 MS/s
    { 164, waveform_164, ifconfig_164 }, // 640 kS/s
    { 150, waveform_150, ifconfig_150 }, // 500 kS/s
    { 140, waveform_140, ifconfig_140 }, // 400 kS/s
    { 120, waveform_120, ifconfig_120 }, // 200 kS/s
    { 113, waveform_113, ifconfig_113 }, // 128 kS/s
    { 110, waveform_110, ifconfig_110 }, // 100 kS/s
    { 106, waveform_106, ifconfig_106 }, //  64 kS/s
    { 105, waveform_105, ifconfig_105 }, //  50 kS/s
    { 104, waveform_104, ifconfig_104 }, //  40 kS/s
    { 103, waveform_103, ifconfig_103 }, //  32 kS/s
    { 102, waveform_102, ifconfig_102 }, //  20 kS/s
};


static BOOL set_samplerate( BYTE rate ) {
    BYTE i = 0;
    const BYTE *waveform;

    while ( samplerates[ i ].rate != rate ) {
        ++i;
        if ( i == sizeof( samplerates ) / sizeof( samplerates[ 0 ] ) )
            return FALSE; // not found
    }

    IFCONFIG = samplerates[ i ].ifconfig;

    waveform = samplerates[ i ].waveform;

    AUTOPTRSETUP = 7;
    AUTOPTRH2 = 0xE4; /* 0xE400: GPIF waveform descriptor 0. */
    AUTOPTRL2 = 0x00;

    i = 32;
    while ( i-- ) // setup waveform 0
        EXTAUTODAT2 = *waveform++;

    i = 96;
    while ( i-- ) // clear waveform 1,2,3
        EXTAUTODAT2 = 0;

    return TRUE;
}


// new functon to set the calibration pulse frequency that allows
// to set all possible frequencies between 32 Hz and 100 kHz
// integer dividers of 2MHz will be exact
// frequencies between 40 Hz and 1000 Hz can be multiples of 10 Hz
// frequencies between 100 Hz and 5500 Hz can be multiples of 100 Hz
// frequencies between 1 kHz and 100 kHz can be multiples of 1 kHz
// calibration frequency is coded into one byte parameter freq:
// freq == 0   -> 100 Hz (compatibility to old sigrok coding)
// freq 1..100 -> freq in kHz
// freq 101, 102 -> not possible
// freq == 103 -> 32 Hz (lowest possible frequency due to 16bit HW timer2)
// freq 104..200  -> (value-100)*10 is freq in Hz (40, 50, ... 1000)
// freq 201..255  -> (value-200)*100 is freq in Hz (100, 200, ... 5500)
// e.g. 105 -> 50 Hz, 216 -> 1600 Hz, 20 -> 20 kHz
//
static BOOL set_calibration_pulse( BYTE freq ) {
    long frequency;
    if ( 0 == freq ) // special case for 100 Hz (sigrok)
        frequency = 100;
    else if ( freq <= 100 ) // 1..100 -> 1..100 kHz
        frequency = freq * 1000L;
    else if ( freq == 103 ) // special case for 32 Hz
        frequency = 32;
    else if ( freq <= 200 ) // 101..200 -> (10, 20, 30,) 40 ... 1000 Hz
        frequency = ( freq - 100 ) * 10L;
    else // 201..255 -> 100, 200, 300 ... 5500 Hz
        frequency = ( freq - 200 ) * 100L;
    if ( frequency < 32L || frequency > 100000L )
        return FALSE; // out of range
    ledinit = frequency / 2;
    long rcap = -2e6L / frequency;
    RCAP2L = rcap & 0xff;
    RCAP2H = ( rcap & 0xff00 ) >> 8;
    return TRUE;
}


/* Set *alt_ifc to the current alt interface for ifc. */
BOOL handle_get_interface( BYTE ifc, BYTE *alt_ifc ) {
    (void)ifc;
    *alt_ifc = altiface;
    return TRUE;
}


/*
 * Return TRUE if you set the interface requested.
 *
 * Note: This function should reconfigure and reset the endpoints
 * according to the interface descriptors you provided.
 */
BOOL handle_set_interface( BYTE ifc, BYTE alt_ifc ) {
    if ( ifc == 0 )
        select_interface( alt_ifc );

    return TRUE;
}


BYTE handle_get_configuration( void ) {
    /* We only support configuration 0. */
    return 0;
}


BOOL handle_set_configuration( BYTE cfg ) {
    /* We only support configuration 0. */
    (void)cfg;
    return TRUE;
}


// handle reading and writing EEPROM data
static BOOL eeprom() {
    WORD addr = SETUP_VALUE(), len = SETUP_LENGTH();
    // 24C02 (small adr mode) recognizes i2c adresses 0x50..0x57
    // 24C128 (large adr mode) must be wired to address 0x51
    const BYTE I2C_EEPROM = 0x51;
    // wait for ep0 not busy
    while ( EP0CS & bmEPBUSY )
        ;
    switch ( SETUP_TYPE ) {
    case 0xc0:                                   // read access
        while ( len ) {                          // still have bytes to read
            BYTE cur_read = len > 64 ? 64 : len; // can't read more than 64 bytes at a time
            while ( EP0CS & bmEPBUSY )           // can't do this until EP0 is ready
                ;
            eeprom_read( I2C_EEPROM, addr, cur_read, EP0BUF );
            EP0BCH = 0;
            SYNCDELAY;
            EP0BCL = cur_read;
            len -= cur_read;
            addr += cur_read;
        }
        break;
    case 0x40: // write access
        while ( len ) {
            BYTE cur_write;
            // printf ( "Len More Bytes %d\n" , len );
            EP0BCL = 0;                // allow pc transfer in
            while ( EP0CS & bmEPBUSY ) // wait
                ;
            cur_write = EP0BCL;
            // printf ( "Writing %d Bytes to %d..\n", cur_write, addr );
            if ( !eeprom_write( I2C_EEPROM, addr, cur_write, EP0BUF ) )
                return FALSE;
            addr += cur_write;
            len -= cur_write;
        }
        break;
    default:
        return FALSE; // bad type
    }
    return TRUE;
}


BOOL handle_get_descriptor() { return FALSE; }


BOOL handle_vendorcommand( BYTE cmd ) {
    stop_sampling();

    /* Set red LED, toggle after timeout. */
    LED_RED();
    ledcounter = ledinit;
    /* Clear EP0BCH/L for each valid command. */
    if ( cmd >= 0xe0 && cmd <= 0xe6 ) {
        EP0BCH = 0;
        EP0BCL = 0;
        while ( EP0CS & bmEPBUSY )
            ;
    }

    switch ( cmd ) {
    case 0xa2:
        return eeprom();

    case 0xe0:
        return set_voltage( 0, EP0BUF[ 0 ] );

    case 0xe1:
        return set_voltage( 1, EP0BUF[ 0 ] );

    case 0xe2:
        return set_samplerate( EP0BUF[ 0 ] );

    case 0xe3:
        if ( EP0BUF[ 0 ] == 1 ) {
            /* Set green LED while sampling. */
            LED_GREEN();
            ledcounter = 0;
            start_sampling();
        }
        return TRUE;

    case 0xe4:
        return set_numchannels( EP0BUF[ 0 ] );

    case 0xe5:
        return set_coupling( EP0BUF[ 0 ] );

    case 0xe6:
        return set_calibration_pulse( EP0BUF[ 0 ] );
    }

    return FALSE; /* Not handled by handlers. */
}


static void init( void ) {
    EP4CFG = 0;
    EP8CFG = 0;

    SET_ANALOG_MODE();

    /* In idle mode tristate all outputs. */
    GPIFIDLECTL = 0x00; /* Don't enable CTL0-5 outputs. */
    GPIFCTLCFG = 0x80;  /* TRICTL=1. CTL0-2: CMOS outputs, tri-statable. */
    GPIFWFSELECT = 0x00;
    GPIFREADYSTAT = 0x00;

    stop_sampling();

    set_voltage( 0, 1 );
    set_voltage( 1, 1 );
    set_samplerate( 1 );
    set_numchannels( 2 );
    select_interface( 0 );
}


// EZ-USB® FX2LP™ Unique ID Registers – KBA89285
// Question:
// Is there a die ID or a unique ID on each EZ-USB® FX2LP™ chip
// that can be used in the application firmware?
// Answer:
// Yes. The FX2LP chips have a 6-byte unique ID that can be read and used
// in the application firmware by customers. This ID is present at these
// register addresses: 0xE507, 0xE508, 0xE509, 0xE50A, 0xE50B, and 0xE50C.
// The most significant byte is present at address 0xE50C,
// and the least significant byte is present at address 0xE507.
// Please make sure to read and store the ID in that order.

__xdata __at 0xE507 volatile BYTE UNIQID[ 6 ]; // 6 ID register bytes little endian

extern __code BYTE serial_num; // defined in descriptor.asm file for the serial number

// array used to convert hex to ascii
static const char hex2Ascii[ 16 ] = { '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F' };

static void insert_serial_number() {
    // string starts at position 2 of string_descriptor
    BYTE __xdata * p_serial_num = (BYTE __xdata *)&serial_num + 2;

    BYTE bbb = 6; // start with MSB
    while ( bbb-- ) {
        // IMPORTANT: be compatible with previous (wrong) implementation
        // write lower nibble before upper nibble to get same serial number
        *p_serial_num++ = hex2Ascii[ UNIQID[ bbb ] & 0x0F ]; // 1. lower nibble
        *p_serial_num++ = 0; // (UTF-16 coding)
        *p_serial_num++ = hex2Ascii[ UNIQID[ bbb ] >> 4 ];   // 2. upper nibble
        *p_serial_num++ = 0; // (UTF-16 coding)
    }
}


void main( void ) {
    /* set to 48 MHz */
    SETCPUFREQ( CPU_FREQ );

    insert_serial_number();

    init();

    /* Set up interrupts. */
    USE_USB_INTS();

    ENABLE_SUDAV();
    ENABLE_USBRESET();
    ENABLE_HISPEED();
    ENABLE_SUSPEND();
    ENABLE_RESUME();

    /* Global (8051) interrupt enable. */
    EA = 1;

    /* Init timer2. */
    RCAP2L = -TIMER2_VAL & 0xff;
    RCAP2H = ( -TIMER2_VAL & 0xff00 ) >> 8;
    T2CON = 0;
    ET2 = 1;
    TR2 = 1;

    RENUMERATE_UNCOND();
    // RENUMERATE();
    // USBCS &= ~bmDISCON;

    // Init the ports with values defined in the scopeXXXX.c files
    // Setting PORTECFG.2 = 1 enables PE.2 as T2OUT that gives a
    // pulse when T2 overflows with double calibration frequency.
    // Toggle a flipflop to get a jitter-free HW calibration signal.
    PORTECFG = INIT_PORTECFG;
    PORTCCFG = INIT_PORTCCFG;
    PORTACFG = INIT_PORTACFG;
    IOE = INIT_IOE;
    IOC = INIT_IOC;
    IOA = INIT_IOA;
    OEE = INIT_OEE;
    OEC = INIT_OEC;
    OEA = INIT_OEA;

    LED_RED();

    while ( TRUE ) {
        if ( dosud ) {
            dosud = FALSE;
            handle_setupdata();
        }

        if ( dosuspend ) {
            dosuspend = FALSE;
            do {
                /* Make sure ext wakeups are cleared. */
                WAKEUPCS |= bmWU | bmWU2;
                SUSPEND = 1;
                PCON |= 1;
                __asm nop __endasm;
                __asm nop __endasm;
                __asm nop __endasm;
                __asm nop __endasm;
                __asm nop __endasm;
                __asm nop __endasm;
                __asm nop __endasm;
            } while ( !remote_wakeup_allowed && REMOTE_WAKEUP() );

            /* Resume (TRM 6.4). */
            if ( REMOTE_WAKEUP() ) {
                delay( 5 );
                USBCS |= bmSIGRESUME;
                delay( 15 );
                USBCS &= ~bmSIGRESUME;
            }
        }
    }
}
