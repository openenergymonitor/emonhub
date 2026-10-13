#!/usr/bin/env python

# **********************************************************************************
# Registers used in driver definition for HopeRF RFM69W/RFM69HW, Semtech SX1231/1231H
# **********************************************************************************
# Copyright Felix Rusu (2014), felix@lowpowerlab.com
# http://lowpowerlab.com/
# **********************************************************************************
# This program is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later version.
# Licence can be viewed at http://www.fsf.org/licenses/gpl.txt
# **********************************************************************************
# Reduced to only the definitions used by the cut down driver in radio.py, the full
# set is available in the LowPowerLabs RFM69 library and in rpi-rfm69.
# **********************************************************************************

# RFM69/SX1231 internal register addresses
REG_FIFO = 0x00
REG_OPMODE = 0x01
REG_DATAMODUL = 0x02
REG_BITRATEMSB = 0x03
REG_BITRATELSB = 0x04
REG_FDEVMSB = 0x05
REG_FDEVLSB = 0x06
REG_FRFMSB = 0x07
REG_FRFMID = 0x08
REG_FRFLSB = 0x09
REG_OSC1 = 0x0A
REG_PALEVEL = 0x11
REG_OCP = 0x13
REG_RXBW = 0x19
REG_RSSIVALUE = 0x24
REG_DIOMAPPING1 = 0x25
REG_IRQFLAGS1 = 0x27
REG_IRQFLAGS2 = 0x28
REG_RSSITHRESH = 0x29
REG_SYNCCONFIG = 0x2E
REG_SYNCVALUE1 = 0x2F
REG_SYNCVALUE2 = 0x30
REG_PACKETCONFIG1 = 0x37
REG_PAYLOADLENGTH = 0x38
REG_FIFOTHRESH = 0x3C
REG_PACKETCONFIG2 = 0x3D
REG_AESKEY1 = 0x3E
REG_TEMP1 = 0x4E
REG_TEMP2 = 0x4F
REG_TESTPA1 = 0x5A #only present on RFM69HW/SX1231H
REG_TESTPA2 = 0x5C #only present on RFM69HW/SX1231H
REG_TESTDAGC = 0x6F

# RegOpMode
RF_OPMODE_SEQUENCER_ON = 0x00  # Default
RF_OPMODE_LISTEN_OFF = 0x00  # Default
RF_OPMODE_SLEEP = 0x00
RF_OPMODE_STANDBY = 0x04  # Default
RF_OPMODE_TRANSMITTER = 0x0C
RF_OPMODE_RECEIVER = 0x10

# RegDataModul
RF_DATAMODUL_DATAMODE_PACKET = 0x00  # Default
RF_DATAMODUL_MODULATIONTYPE_FSK = 0x00  # Default
RF_DATAMODUL_MODULATIONSHAPING_00 = 0x00  # Default

# RegBitRate (bits/sec) example bit rates
RF_BITRATEMSB_55555 = 0x02
RF_BITRATELSB_55555 = 0x40

# RegFdev - frequency deviation (Hz)
RF_FDEVMSB_50000 = 0x03
RF_FDEVLSB_50000 = 0x33

# RegFrf (MHz) - carrier frequency
RF_FRFMSB_315 = 0x4E
RF_FRFMID_315 = 0xC0
RF_FRFLSB_315 = 0x00
RF_FRFMSB_433 = 0x6C
RF_FRFMID_433 = 0x40
RF_FRFLSB_433 = 0x00
RF_FRFMSB_433_92 = 0x6C
RF_FRFMID_433_92 = 0x7A
RF_FRFLSB_433_92 = 0xE1
RF_FRFMSB_868 = 0xD9
RF_FRFMID_868 = 0x00
RF_FRFLSB_868 = 0x00
RF_FRFMSB_915 = 0xE4  # Default
RF_FRFMID_915 = 0xC0  # Default
RF_FRFLSB_915 = 0x00  # Default

# RegOsc1
RF_OSC1_RCCAL_START = 0x80
RF_OSC1_RCCAL_DONE = 0x40

# RegPaLevel
RF_PALEVEL_PA0_ON = 0x80  # Default
RF_PALEVEL_PA1_ON = 0x40
RF_PALEVEL_PA1_OFF = 0x00  # Default
RF_PALEVEL_PA2_ON = 0x20
RF_PALEVEL_PA2_OFF = 0x00  # Default
RF_PALEVEL_OUTPUTPOWER_11111 = 0x1F  # Default

# RegOcp
RF_OCP_OFF = 0x0F
RF_OCP_ON = 0x1A  # Default

# RegRxBw
RF_RXBW_DCCFREQ_010 = 0x40  # Default
RF_RXBW_MANT_16 = 0x00
RF_RXBW_EXP_2 = 0x02

# RegDioMapping1
RF_DIOMAPPING1_DIO0_00 = 0x00  # Default
RF_DIOMAPPING1_DIO0_01 = 0x40

# RegIrqFlags1
RF_IRQFLAGS1_MODEREADY = 0x80

# RegIrqFlags2
RF_IRQFLAGS2_PACKETSENT = 0x08
RF_IRQFLAGS2_PAYLOADREADY = 0x04

# RegSyncConfig
RF_SYNC_ON = 0x80  # Default
RF_SYNC_FIFOFILL_AUTO = 0x00  # Default -- when sync interrupt occurs
RF_SYNC_SIZE_2 = 0x08
RF_SYNC_TOL_0 = 0x00  # Default

# RegPacketConfig1
RF_PACKET1_FORMAT_VARIABLE = 0x80
RF_PACKET1_DCFREE_OFF = 0x00  # Default
RF_PACKET1_CRC_ON = 0x10  # Default
RF_PACKET1_CRCAUTOCLEAR_ON = 0x00  # Default
RF_PACKET1_ADRSFILTERING_OFF = 0x00  # Default

# RegFifoThresh
RF_FIFOTHRESH_TXSTART_FIFONOTEMPTY = 0x80  # Default
RF_FIFOTHRESH_VALUE = 0x0F  # Default

# RegPacketConfig2
RF_PACKET2_RXRESTARTDELAY_2BITS = 0x10
RF_PACKET2_RXRESTART = 0x04
RF_PACKET2_AUTORXRESTART_ON = 0x02  # Default
RF_PACKET2_AES_ON = 0x01
RF_PACKET2_AES_OFF = 0x00  # Default

# RegTemp1
RF_TEMP1_MEAS_START = 0x08
RF_TEMP1_MEAS_RUNNING = 0x04

# RegTestDagc 0x6F: demodulator config and IO mode config
RF_DAGC_IMPROVED_LOWBETA0 = 0x30  # Recommended default

# Frequency bands, radio modes and driver constants
RF69_315MHZ = 31  # non trivial values to avoid misconfiguration
RF69_433MHZ = 43
RF69_433_92MHZ = 49
RF69_868MHZ = 86
RF69_915MHZ = 91
CSMA_LIMIT = -90 # upper RX signal sensitivity threshold in dBm for carrier sense access
RF69_MODE_SLEEP = 0 # XTAL OFF
RF69_MODE_STANDBY = 1 # XTAL ON
RF69_MODE_RX = 3 # RX MODE
RF69_MODE_TX = 4 # TX MODE
COURSE_TEMP_COEF = -90 # puts the temperature reading in the ballpark, user can fine tune the returned value
RF69_BROADCAST_ADDR = 255
RF69_CSMA_LIMIT_S = 1
