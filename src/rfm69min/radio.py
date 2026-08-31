"""Minimal RFM69 radio driver for the Raspberry Pi (LowPowerLabs packet format)

Cut down from the rpi-rfm69 library https://github.com/openenergymonitor/rpi-rfm69
(itself a port of the LowPowerLabs RFM69 Arduino library by Felix Rusu) to only
the receive side used by EmonHubRFM69LPLInterfacer: configure the radio, receive
packets and acknowledge them when the sender asks. Transmit, listen mode and
asyncio support have all been removed.

Original library GPL v3, LowPowerLabs register definitions GPL v2 or later.
"""

import time

import spidev
import RPi.GPIO as GPIO

from .registers import *


class Packet(object):
    """A received radio packet

    Args:
        receiver (int): Node ID of receiver
        sender (int): Node ID of sender
        RSSI (int): Received Signal Strength Indicator i.e. the power present in a received radio signal
        data (list): Raw transmitted data

    """

    __slots__ = 'receiver', 'sender', 'RSSI', 'data'

    def __init__(self, receiver, sender, RSSI, data):
        self.receiver = receiver
        self.sender = sender
        self.RSSI = RSSI
        self.data = data


frfMSB = {RF69_315MHZ: RF_FRFMSB_315, RF69_433MHZ: RF_FRFMSB_433, RF69_433_92MHZ: RF_FRFMSB_433_92, RF69_868MHZ: RF_FRFMSB_868, RF69_915MHZ: RF_FRFMSB_915}
frfMID = {RF69_315MHZ: RF_FRFMID_315, RF69_433MHZ: RF_FRFMID_433, RF69_433_92MHZ: RF_FRFMID_433_92, RF69_868MHZ: RF_FRFMID_868, RF69_915MHZ: RF_FRFMID_915}
frfLSB = {RF69_315MHZ: RF_FRFLSB_315, RF69_433MHZ: RF_FRFLSB_433, RF69_433_92MHZ: RF_FRFLSB_433_92, RF69_868MHZ: RF_FRFLSB_868, RF69_915MHZ: RF_FRFLSB_915}


def get_config(freqBand, networkID):
    return {
          0x01: [REG_OPMODE, RF_OPMODE_SEQUENCER_ON | RF_OPMODE_LISTEN_OFF | RF_OPMODE_STANDBY],
          #no shaping
          0x02: [REG_DATAMODUL, RF_DATAMODUL_DATAMODE_PACKET | RF_DATAMODUL_MODULATIONTYPE_FSK | RF_DATAMODUL_MODULATIONSHAPING_00],
          #default:4.8 KBPS
          0x03: [REG_BITRATEMSB, RF_BITRATEMSB_55555],
          0x04: [REG_BITRATELSB, RF_BITRATELSB_55555],
          #default:5khz, (FDEV + BitRate/2 <= 500Khz)
          0x05: [REG_FDEVMSB, RF_FDEVMSB_50000],
          0x06: [REG_FDEVLSB, RF_FDEVLSB_50000],

          0x07: [REG_FRFMSB, frfMSB[freqBand]],
          0x08: [REG_FRFMID, frfMID[freqBand]],
          0x09: [REG_FRFLSB, frfLSB[freqBand]],

          # RXBW defaults are { REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_24 | RF_RXBW_EXP_5} (RxBw: 10.4khz)
          #//(BitRate < 2 * RxBw)
          0x19: [REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_16 | RF_RXBW_EXP_2],
          #DIO0 is the only IRQ we're using
          0x25: [REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01],
          #must be set to dBm = (-Sensitivity / 2) - default is 0xE4=228 so -114dBm
          0x29: [REG_RSSITHRESH, 220],
          0x2e: [REG_SYNCCONFIG, RF_SYNC_ON | RF_SYNC_FIFOFILL_AUTO | RF_SYNC_SIZE_2 | RF_SYNC_TOL_0],
          #attempt to make this compatible with sync1 byte of RFM12B lib
          0x2f: [REG_SYNCVALUE1, 0x2D],
          #NETWORK ID
          0x30: [REG_SYNCVALUE2, networkID],
          0x37: [REG_PACKETCONFIG1, RF_PACKET1_FORMAT_VARIABLE | RF_PACKET1_DCFREE_OFF |
                RF_PACKET1_CRC_ON | RF_PACKET1_CRCAUTOCLEAR_ON | RF_PACKET1_ADRSFILTERING_OFF],
          #in variable length mode: the max frame size, not used in TX
          0x38: [REG_PAYLOADLENGTH, 66],
          #TX on FIFO not empty
          0x3C: [REG_FIFOTHRESH, RF_FIFOTHRESH_TXSTART_FIFONOTEMPTY | RF_FIFOTHRESH_VALUE],
          #RXRESTARTDELAY must match transmitter PA ramp-down time (bitrate dependent)
          0x3d: [REG_PACKETCONFIG2, RF_PACKET2_RXRESTARTDELAY_2BITS | RF_PACKET2_AUTORXRESTART_ON | RF_PACKET2_AES_OFF],
          # run DAGC continuously in RX mode, recommended default for AfcLowBetaOn=0
          0x6F: [REG_TESTDAGC, RF_DAGC_IMPROVED_LOWBETA0],
          0x00: [255, 0]
        }


class Radio(object):

    def __init__(self, freqBand, nodeID, networkID=100, **kwargs):
        """RFM69 Radio interface for the Raspberry PI.

        An RFM69 module is expected to be connected to the SPI interface of the Raspberry Pi.
        The class is a context manager so you can instantiate it using the 'with' keyword.

        Args:
            freqBand: Frequency band of radio - 315MHz, 433MHz, 868Mhz or 915MHz.
            nodeID (int): The node ID of this device.
            networkID (int): The network ID

        Keyword Args:
            auto_acknowledge (bool): Automatically send acknowledgements
            isHighPower (bool): Is this a high power radio model
            power (int): Power level - a percentage in range 10 to 100.
            interruptPin (int): Pin number of interrupt pin. This is a pin index not a GPIO number.
            resetPin (int): Pin number of reset pin. This is a pin index not a GPIO number.
            selPin (int): Pin number of chip select pin. This is a pin index not a GPIO number.
            spiBus (int): SPI bus number.
            spiDevice (int): SPI device number.
            promiscuousMode (bool): Listen to all messages not just those addressed to this node ID.
            encryptionKey (str): 16 character encryption key.

        """
        self.auto_acknowledge = kwargs.get('autoAcknowledge', True)
        self.isRFM69HW = kwargs.get('isHighPower', True)
        self.intPin = kwargs.get('interruptPin', 18)
        self.rstPin = kwargs.get('resetPin', 29)
        self.selPin = kwargs.get('selPin', 16)
        self.spiBus = kwargs.get('spiBus', 0)
        self.spiDevice = kwargs.get('spiDevice', 0)
        self.promiscuousMode = kwargs.get('promiscuousMode', 0)

        self.intLock = False
        self.mode = ""

        self.packets = []

        self._init_spi()
        self._init_gpio()
        self.init_success = self._initialize(freqBand, nodeID, networkID)
        if self.init_success:
            self._encrypt(kwargs.get('encryptionKey', 0))
            self.set_power_level(kwargs.get('power', 70))

    def _initialize(self, freqBand, nodeID, networkID):
        if not self._reset_radio(): return False

        self._set_config(get_config(freqBand, networkID))
        self._setHighPower(self.isRFM69HW)
        # Wait for ModeReady
        start = time.time()
        while (self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            if time.time() - start > 1.0:
                return False

        self.address = nodeID
        self._init_interrupt()

        return True

    def _init_gpio(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.intPin, GPIO.IN)
        if self.rstPin:
            GPIO.setup(self.rstPin, GPIO.OUT)
        GPIO.setup(self.selPin, GPIO.OUT)

    def _init_spi(self):
        #initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(self.spiBus, self.spiDevice)
        self.spi.max_speed_hz = 4000000
        self.spi.no_cs = True

    def select(self):
        GPIO.output(self.selPin, GPIO.LOW)

    def unselect(self):
        GPIO.output(self.selPin, GPIO.HIGH)

    def _reset_radio(self):
        # Hard reset the RFM module
        if self.rstPin:
            GPIO.output(self.rstPin, GPIO.HIGH)
            time.sleep(0.3)
            GPIO.output(self.rstPin, GPIO.LOW)
            time.sleep(0.3)
        #verify chip is syncing?
        start = time.time()
        while self._readReg(REG_SYNCVALUE1) != 0xAA:
            self._writeReg(REG_SYNCVALUE1, 0xAA)
            if time.time() - start > 0.1:
                return False
        start = time.time()
        while self._readReg(REG_SYNCVALUE1) != 0x55:
            self._writeReg(REG_SYNCVALUE1, 0x55)
            if time.time() - start > 0.1:
                return False
        return True

    def _set_config(self, config):
        for value in config.values():
            self._writeReg(value[0], value[1])

    def _init_interrupt(self):
        GPIO.remove_event_detect(self.intPin)
        GPIO.add_event_detect(self.intPin, GPIO.RISING, callback=self._interruptHandler)

    #
    # End of Init
    #

    def __enter__(self):
        """When the context begins"""
        self.read_temperature()
        self.calibrate_radio()
        self.begin_receive()
        return self

    def __exit__(self, *args):
        """When context exits (including when the script is terminated)"""
        self._shutdown()

    def sleep(self):
        """Put the radio into sleep mode"""
        self._setMode(RF69_MODE_SLEEP)

    def set_power_level(self, percent):
        """Set the transmit power level

        Args:
            percent (int): Value between 0 and 100.

        """
        assert type(percent) == int
        self.powerLevel = int( round(31 * (percent / 100)))
        self._writeReg(REG_PALEVEL, (self._readReg(REG_PALEVEL) & 0xE0) | self.powerLevel)

    def read_temperature(self, calFactor=0):
        """Read the temperature of the radios CMOS chip.

        Args:
            calFactor: Additional correction to corrects the slope, rising temp = rising val

        Returns:
            int: Temperature in centigrade
        """
        self._setMode(RF69_MODE_STANDBY)
        self._writeReg(REG_TEMP1, RF_TEMP1_MEAS_START)
        while self._readReg(REG_TEMP1) & RF_TEMP1_MEAS_RUNNING:
            pass
        # COURSE_TEMP_COEF puts reading in the ballpark, user can add additional correction
        #'complement'corrects the slope, rising temp = rising val
        return (int(~self._readReg(REG_TEMP2)) * -1) + COURSE_TEMP_COEF + calFactor

    def calibrate_radio(self):
        """Calibrate the internal RC oscillator for use in wide temperature variations.

        See RFM69 datasheet section [4.3.5. RC Timer Accuracy] for more information.
        """
        self._writeReg(REG_OSC1, RF_OSC1_RCCAL_START)
        while self._readReg(REG_OSC1) & RF_OSC1_RCCAL_DONE == 0x00:
            pass

    def begin_receive(self):
        """Begin listening for packets"""
        while self.intLock:
            time.sleep(.1)

        if (self._readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY):
            # avoid RX deadlocks
            self._writeReg(REG_PACKETCONFIG2, (self._readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        #set DIO0 to "PAYLOADREADY" in receive mode
        self._writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01)
        self._setMode(RF69_MODE_RX)

    def has_received_packet(self):
        """Check if packet received

        Returns:
            bool: True if packet has been received

        """
        return len(self.packets) > 0

    def get_packet(self):
        """Get next received packet.

        Returns:
            Packet: A single Packet, or False if none are waiting.
        """
        if len(self.packets):
            return self.packets.pop(0)
        else:
            return False

    def send_ack(self, toAddress):
        """Send an empty acknowledgement packet

        Args:
            toAddress (int): Recipient node's ID

        """
        # Wait for a clear channel, giving up rather than blocking indefinitely
        now = time.time()
        while (not self._canSend()) and time.time() - now < RF69_CSMA_LIMIT_S:
            time.sleep(0.01)

        #turn off receiver to prevent reception while filling fifo
        self._setMode(RF69_MODE_STANDBY)
        #wait for modeReady
        while (self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            pass
        # DIO0 is "Packet Sent"
        self._writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_00)

        # payload length 3 (target, sender, CTL), CTL byte 0x80 marks this as an ACK
        self.select()
        self.spi.xfer2([REG_FIFO | 0x80, 3, toAddress, self.address, 0x80])
        self.unselect()

        self._setMode(RF69_MODE_TX)
        while ((self._readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PACKETSENT) == 0x00):
            time.sleep(0.01)
            pass # make sure packet is sent before putting more into the FIFO

        self._setMode(RF69_MODE_RX)

    #
    # Internal functions
    #

    def _setMode(self, newMode):
        if newMode == self.mode:
            return
        if newMode == RF69_MODE_TX:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_TRANSMITTER)
            if self.isRFM69HW:
                self._setHighPowerRegs(True)
        elif newMode == RF69_MODE_RX:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_RECEIVER)
            if self.isRFM69HW:
                self._setHighPowerRegs(False)
        elif newMode == RF69_MODE_STANDBY:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_STANDBY)
        elif newMode == RF69_MODE_SLEEP:
            self._writeReg(REG_OPMODE, (self._readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SLEEP)
        else:
            return
        # we are using packet mode, so this check is not really needed
        # but waiting for mode ready is necessary when going from sleep because the FIFO may not be immediately available from previous mode
        while self.mode == RF69_MODE_SLEEP and self._readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY == 0x00:
            pass
        self.mode = newMode

    def _canSend(self):
        if self.mode == RF69_MODE_STANDBY:
            self.begin_receive()
            return True
        #if signal stronger than -100dBm is detected assume channel activity
        elif self.mode == RF69_MODE_RX and self._readRSSI() < CSMA_LIMIT:
            self._setMode(RF69_MODE_STANDBY)
            return True
        return False

    def _readRSSI(self):
        rssi = self._readReg(REG_RSSIVALUE) * -1
        rssi = rssi >> 1
        return rssi

    def _encrypt(self, key):
        self._setMode(RF69_MODE_STANDBY)
        if key != 0 and len(key) == 16:
            self.select()
            self.spi.xfer([REG_AESKEY1 | 0x80] + [int(ord(i)) for i in list(key)])
            self.unselect()
            self._writeReg(REG_PACKETCONFIG2,(self._readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_ON)
        else:
            self._writeReg(REG_PACKETCONFIG2,(self._readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_OFF)

    def _readReg(self, addr):
        self.select()
        regval = self.spi.xfer([addr & 0x7F, 0])[1]
        self.unselect()
        return regval

    def _writeReg(self, addr, value):
        self.select()
        self.spi.xfer([addr | 0x80, value])
        self.unselect()

    def _setHighPower(self, onOff):
        if onOff:
            self._writeReg(REG_OCP, RF_OCP_OFF)
            #enable P1 & P2 amplifier stages
            self._writeReg(REG_PALEVEL, (self._readReg(REG_PALEVEL) & 0x1F) | RF_PALEVEL_PA1_ON | RF_PALEVEL_PA2_ON)
        else:
            self._writeReg(REG_OCP, RF_OCP_ON)
            #enable P0 only
            self._writeReg(REG_PALEVEL, RF_PALEVEL_PA0_ON | RF_PALEVEL_PA1_OFF | RF_PALEVEL_PA2_OFF | RF_PALEVEL_OUTPUTPOWER_11111)

    def _setHighPowerRegs(self, onOff):
        if onOff:
            self._writeReg(REG_TESTPA1, 0x5D)
            self._writeReg(REG_TESTPA2, 0x7C)
        else:
            self._writeReg(REG_TESTPA1, 0x55)
            self._writeReg(REG_TESTPA2, 0x70)

    def _shutdown(self):
        """Shutdown the radio.

        Puts the radio to sleep and cleans up the GPIO connections.
        """
        self._setHighPower(False)
        self.sleep()
        GPIO.cleanup()

    def __str__(self):
        return "Radio RFM69"

    def __repr__(self):
        return "Radio()"

    #
    # Radio interrupt handler
    #

    def _interruptHandler(self, pin):
        self.intLock = True

        if self.mode == RF69_MODE_RX and self._readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY:
            self._setMode(RF69_MODE_STANDBY)

            self.select()
            payload_length, target_id, sender_id, CTLbyte = self.spi.xfer2([REG_FIFO & 0x7f,0,0,0,0])[1:]
            self.unselect()

            if payload_length > 66:
                payload_length = 66

            if not (self.promiscuousMode or target_id == self.address or target_id == RF69_BROADCAST_ADDR):
                self.intLock = False
                self.begin_receive()
                return

            data_length = payload_length - 3
            ack_received  = bool(CTLbyte & 0x80)
            ack_requested = bool(CTLbyte & 0x40)
            self.select()
            data = self.spi.xfer2([REG_FIFO & 0x7f] + [0 for i in range(0, data_length)])[1:]
            self.unselect()
            rssi = self._readRSSI()

            # When message received (acknowledgements are not data and are discarded,
            # nothing here requests them)
            if not ack_received:
                self.packets.append(
                    Packet(int(target_id), int(sender_id), int(rssi), list(data))
                )

            # Send acknowledgement if needed
            if ack_requested and self.auto_acknowledge:
                self.intLock = False
                self.send_ack(sender_id)

        self.intLock = False
        self.begin_receive()
