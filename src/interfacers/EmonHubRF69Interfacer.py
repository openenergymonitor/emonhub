from emonhub_interfacer import EmonHubInterfacer
import Cargo
import time

"""class EmonHubRF69Interfacer

Read JeeLib format packets directly from an RFM69 module on the RaspberryPi SPI bus

Two packet formats are supported, selected with the format setting, matching the
radio.format() call of the RFM69_JeeLib Arduino library used by the transmitting
nodes:

    format = 1  JeeLib classic, the RFM12B compatible format used by
                OpenEnergyMonitor hardware up to Nov 2022. The RFM69 packet
                engine is switched off and the frame is unpacked and CRC checked
                here.
    format = 2  JeeLib native (default), the RFM69 packet engine handles the
                length byte, whitening and CRC.

Both formats share the same bit rate, deviation, frequency and sync bytes, but a
radio can only listen for one of them at a time.

The radio is polled rather than driven by the DIO0 interrupt, so only the SPI
lines, the select pin and, where the hardware has one, the reset pin need to be
connected. Pin numbers are BOARD numbering, as used by EmonHubRFM69LPLInterfacer,
so the same selPin and resetPin settings apply to the same hardware.

Example emonhub.conf entry, JeeLib native on emonPi2, emonPi3 or emonHP hardware:

    [[SPI]]
        Type = EmonHubRF69Interfacer
        [[[init_settings]]]
            nodeid = 5
            group = 210
            format = 2        # 1 = JeeLib classic, 2 = JeeLib native
            resetPin = 24     # remove line if hardware is emonBase RFM69 SPI
            selPin = 16       # remove line or change to selPin = 26 if hardware is emonBase RFM69 SPI
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,

and JeeLib classic on an emonBase RFM69 SPI adaptor, which has no reset pin:

    [[SPI]]
        Type = EmonHubRF69Interfacer
        [[[init_settings]]]
            nodeid = 5
            group = 210
            format = 1
            selPin = 26
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,

"""

REG_FIFO          = 0x00
REG_OPMODE        = 0x01
REG_RSSIVALUE     = 0x24
REG_IRQFLAGS1     = 0x27
REG_IRQFLAGS2     = 0x28
REG_SYNCVALUE1    = 0x2F
REG_SYNCVALUE2    = 0x30
MODE_RECEIVE      = 4<<2
IRQ1_MODEREADY    = 1<<7
IRQ2_PAYLOADREADY = 1<<2

# Give up on a register that never reads back rather than block the thread
REG_POLL_TIMEOUT_S = 0.1

JEELIB_CLASSIC    = 1
JEELIB_NATIVE     = 2

# Size of the radio FIFO, a whole classic frame fits in it
CLASSIC_FRAME_LEN = 66
# Frame is: node byte, length byte, data, CRC16
CLASSIC_MAX_DATA_LEN = CLASSIC_FRAME_LEN - 4

# JeeLib native configuration, as configRegs_v2 in the RFM69_JeeLib library
CONFIG = {
  # POR value is better for first rf_sleep  0x01, 0x00, # OpMode = sleep
  0x01: 0x04, # OpMode = standby
  0x02: 0x00, # DataModul = packet mode, fsk
  0x03: 0x02, # BitRateMsb, data rate = 49,261 bits/s
  0x04: 0x8A, # BitRateLsb, divider = 32 MHz / 650
  0x05: 0x05, # FdevMsb 90 kHz
  0x06: 0xC3, # FdevLsb 90 kHz

  0x07: 0x6C, # 433 Mhz
  0x08: 0x80, # RegFrfMid
  0x09: 0x00, # RegFrfLsb

  0x0B: 0x20, # Low M
  0x11: 0x99, # OutputPower = +7 dBm - was default = max = +13 dBm
  0x19: 0x42, # RxBw 125 kHz
  #0x1A: 0x42, # AfcBw 125 kHz
  0x1E: 0x2C, # AfcAutoclearOn, AfcAutoOn
  #0x25: 0x40, #0x80, # DioMapping1 = SyncAddress (Rx)
  0x26: 0x07, # disable clkout
  0x29: 0xA0, # RssiThresh -80 dB
  0x2D: 0x05, # PreambleSize = 5
  0x2E: 0x88, # SyncConfig = sync on, sync size = 2
  0x2F: 0x2D, # SyncValue1 = 0x2D
  0x37: 0xD0, # PacketConfig1 = variable, white, no filtering
  0x38: 0x42, # PayloadLength = 0, unlimited
  0x3C: 0x8F, # FifoThresh, not empty, level 15
  0x3D: 0x12, # 0x10, # PacketConfig2, interpkt = 1, autorxrestart off
  0x6F: 0x20, # TestDagc ...
  0x71: 0x02  # RegTestAfc
}

# JeeLib classic predates the RFM69 packet engine: frames are not whitened, carry
# their own length byte in second place and their own CRC16, so there is nothing
# for the packet engine to do. Fixed length mode is used rather than unlimited
# length, so that a full FIFO is collected on each sync match and PayloadReady
# still marks a frame as waiting, the alternative being a FIFO that fills with
# noise between reads. Everything else is left as the native configuration, the
# two formats are identical at the radio level.
CLASSIC_CONFIG = dict(CONFIG)
CLASSIC_CONFIG[0x37] = 0x00              # PacketConfig1 = fixed length, no whitening, no CRC
CLASSIC_CONFIG[0x38] = CLASSIC_FRAME_LEN # PayloadLength


def crc16_update(crc, byte):
    """CRC16 as used by JeeLib, the _crc16_update of the avr-libc util/crc16.h"""
    crc ^= byte
    for _ in range(8):
        if crc & 1:
            crc = (crc >> 1) ^ 0xA001
        else:
            crc >>= 1
    return crc


class EmonHubRF69Interfacer(EmonHubInterfacer):

    def __init__(self, name, nodeid, group, format=JEELIB_NATIVE, selPin=16, resetPin=None):
        """Initialize Interfacer

        nodeid (integer): radio nodeid 1-63, 63 receives all
        group (integer): radio group 0-255
        format (integer): 1 for JeeLib classic, 2 for JeeLib native
        selPin (integer): radio select pin, BOARD numbering
        resetPin (integer): radio reset pin, BOARD numbering, None if not wired

        """
        # Initialization, first so that self._log exists for the imports below
        super().__init__(name)

        self.spidev = None
        try:
            import spidev
            self.spidev = spidev
        except ModuleNotFoundError as err:
            self._log.error(err)

        self.GPIO = None
        try:            
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            GPIO.setwarnings(False)
        except ModuleNotFoundError as err:      
            self._log.error(err)
            
        # sudo adduser emonhub spi

        # Watchdog variables
        self.last_received = time.monotonic()
        self.watchdog_period = 300

        self.myId = int(nodeid)
        self.group = int(group)
        self.sel_pin = int(selPin)

        if resetPin != None and resetPin != 'None':
            resetPin = int(resetPin)
        else:
            resetPin = None
        self.reset_pin = resetPin

        self.format = int(format)
        if self.format not in (JEELIB_CLASSIC, JEELIB_NATIVE):
            self._log.error("Invalid RF69 format "+str(self.format)+", using JeeLib native")
            self.format = JEELIB_NATIVE

        self.parity = self.group ^ (self.group << 4)
        self.parity = (self.parity ^ (self.parity << 2)) & 0xC0

        self._log.info("Creating RF69 interfacer")
        self._log.info("RF69 nodeid = "+str(self.myId))
        self._log.info("RF69 group = "+str(self.group))
        self._log.info("RF69 format = "+("JeeLib classic" if self.format == JEELIB_CLASSIC else "JeeLib native"))
        self._log.info("RF69 selPin = "+str(self.sel_pin))
        self._log.info("RF69 resetPin = "+str(self.reset_pin))

        self.spi = None
        self.radio_ok = False
        self.rxMsg = []
        self.rssi = 0
        self.mode = False

        self._log.info("Starting radio setup")
        self.connect()

    def connect(self):
        """Set up the radio, leaves radio_ok False if it cannot be reached"""

        self.radio_ok = False
        self.mode = False
        # Arm the watchdog from here, so that a radio which starts but never
        # receives anything is restarted as well as one that goes quiet
        self.last_received = time.monotonic()

        if not self.spidev or not self.GPIO:
            self._log.error("Cannot connect to RF69, spidev or RPi.GPIO not available")
            return

        try:
            if self.spi is None:
                self.spi = self.spidev.SpiDev()
                self.spi.open(0,1)
                self.spi.max_speed_hz = 4000000
                self.spi.no_cs = True

            # BOARD numbering, matching EmonHubRFM69LPLInterfacer, so that the
            # two interfacers agree on what selPin and resetPin mean and can
            # coexist in one emonhub, RPi.GPIO allows only one numbering mode
            self.GPIO.setmode(self.GPIO.BOARD)
            self.GPIO.setup(self.sel_pin, self.GPIO.OUT)
            if self.reset_pin:
                self.GPIO.setup(self.reset_pin, self.GPIO.OUT)
            self.unselect()

            if not self.reset_radio():
                self._log.error("Could not connect to RF69 module")
                return

            config = CLASSIC_CONFIG if self.format == JEELIB_CLASSIC else CONFIG
            for key, value in config.items():
                self.writeReg(key, value)

            self.writeReg(REG_SYNCVALUE2, self.group)
        except Exception as err:
            self._log.error("Error initializing RF69: "+str(err))
            return

        self.radio_ok = True
        self._log.info("Radio setup complete")

    def reset_radio(self):
        """Reset the radio if the pin is wired and check that it responds"""

        if self.reset_pin:
            self.GPIO.output(self.reset_pin, self.GPIO.HIGH)
            time.sleep(0.3)
            self.GPIO.output(self.reset_pin, self.GPIO.LOW)
            time.sleep(0.3)

        # The radio is only talking to us if it reads back what we write
        for value in (0xAA, 0x55):
            start = time.monotonic()
            while self.readReg(REG_SYNCVALUE1) != value:
                self.writeReg(REG_SYNCVALUE1, value)
                if time.monotonic() - start > REG_POLL_TIMEOUT_S:
                    return False
        return True

    def select(self):
        self.GPIO.output(self.sel_pin, self.GPIO.LOW)

    def unselect(self):
        self.GPIO.output(self.sel_pin, self.GPIO.HIGH)

    def readReg(self,addr):
        self.select()
        regval = self.spi.xfer([addr & 0x7F, 0])[1]
        self.unselect()
        return regval

    def writeReg(self, addr, value):
        self.select()
        self.spi.xfer([addr | 0x80, value])
        self.unselect()
      
    def rfm69_setMode (self,newMode):
        """Change radio mode, returns False if the radio does not become ready"""
        self.mode = newMode
        self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | newMode)
        start = time.monotonic()
        while (self.readReg(REG_IRQFLAGS1) & IRQ1_MODEREADY) == 0x00:
            if time.monotonic() - start > REG_POLL_TIMEOUT_S:
                self._log.error("Timed out waiting for RF69 mode ready")
                return False
        return True
        
    def rfm69_receive (self):
        """Read a JeeLib native frame, returns the payload length or -1

        The frame is [length][group parity + destination][sender][data ...], the
        packet engine has already checked the CRC and removed the whitening.

        """
        if self.mode != MODE_RECEIVE:
            if not self.rfm69_setMode(MODE_RECEIVE):
                self.radio_ok = False
        else:
            if self.readReg(REG_IRQFLAGS2) & IRQ2_PAYLOADREADY:
                # FIFO access
                self.select()
                count = self.spi.xfer([REG_FIFO & 0x7F,0])[1]
                if count:
                    self.rxMsg = self.spi.xfer2([0 for i in range(0, count)])
                self.unselect()
                if count:
                    # only accept packets intended for us, or broadcasts
                    # ... or any packet if we're the special catch-all node
                    self.rssi = self.readReg(REG_RSSIVALUE)
                    dest = self.rxMsg[0]
                    if (dest & 0xC0) == self.parity:
                        destId = dest & 0x3F;
                        if destId == self.myId or destId == 0 or self.myId == 63:
                            return count;

        return -1

    def rfm69_receive_classic (self):
        """Read a JeeLib classic frame, returns [nodeid, data] or None

        The frame is [node][length][data ...][CRC16 low][CRC16 high], with the
        CRC taken over the group byte and everything up to the data. In fixed
        length mode the radio collects a full FIFO after each sync match, so the
        frame sits at the front of what is read out, followed by noise.

        """
        if self.mode != MODE_RECEIVE:
            if not self.rfm69_setMode(MODE_RECEIVE):
                self.radio_ok = False
            return None

        if not self.readReg(REG_IRQFLAGS2) & IRQ2_PAYLOADREADY:
            return None

        # FIFO access, reading the whole payload clears PayloadReady and, with
        # AutoRxRestart set, returns the radio to receive
        self.select()
        frame = self.spi.xfer2([REG_FIFO & 0x7F] + [0 for i in range(0, CLASSIC_FRAME_LEN)])[1:]
        self.unselect()

        length = frame[1]
        if length < 1 or length > CLASSIC_MAX_DATA_LEN:
            return None

        data = frame[2:2 + length]

        crc = 0xFFFF
        for byte in [self.group, frame[0], frame[1]] + data:
            crc = crc16_update(crc, byte)

        if crc != (frame[2 + length] | (frame[3 + length] << 8)):
            return None

        self.rssi = self.readReg(REG_RSSIVALUE)

        # The sender is in the low 5 bits, the JeeLib control bits above it are
        # not used by OpenEnergyMonitor nodes, which only ever broadcast
        return [frame[0] & 0x1F, data]

    def read(self):
        """Read data from RFM69 and process if a complete frame was received

        Returns a Cargo item: [NodeID, val1, val2] or False

        """
        if self.radio_ok:
            c = None
            try:
                if self.format == JEELIB_CLASSIC:
                    frame = self.rfm69_receive_classic()
                    if frame:
                        c = Cargo.new_cargo(rawdata='')
                        c.nodeid = frame[0]
                        c.realdata = frame[1]
                        c.rssi = -0.5*self.rssi
                else:
                    msg_len = self.rfm69_receive()
                    if msg_len > 1:
                        c = Cargo.new_cargo(rawdata='')
                        c.nodeid = self.rxMsg[1]
                        c.realdata = self.rxMsg[2:]
                        c.rssi = -0.5*self.rssi
            except Exception as err:
                self._log.error("Error reading from RF69: "+str(err))
                self.radio_ok = False

            if c:
                # Set watchdog timer
                self.last_received = time.monotonic()
                return c

        # Restart the radio if nothing has been received for the watchdog
        # period, which covers a radio that failed to start as well as one
        # that has stopped receiving
        if (time.monotonic()-self.last_received) > self.watchdog_period:
            self._log.warning("No radio packets received in last "+str(self.watchdog_period)+" seconds, restarting radio")
            self.connect()

        return False

    def set(self, **kwargs):
        """

        """
        # include kwargs from parent
        super().set(**kwargs)
