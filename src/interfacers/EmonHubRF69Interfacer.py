import socket
import select
from emonhub_interfacer import EmonHubInterfacer
import Cargo
import spidev
import RPi.GPIO as GPIO

"""class EmonHubRF69Interfacer

Monitors a socket for data, typically from ethernet link

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

class EmonHubRF69Interfacer(EmonHubInterfacer):

    def __init__(self, name, nodeid, group):
        """Initialize Interfacer

        port_nb (string): port number on which to open the socket

        """

        # Initialization
        super().__init__(name)
        
        self.myId = int(nodeid)
        group = int(group)
        
        self.parity = group ^ (group << 4)
        self.parity = (self.parity ^ (self.parity << 2)) & 0xC0

        self.spi = spidev.SpiDev()
        self.spi.open(0,1)
        self.spi.max_speed_hz = 4000000
        self.spi.no_cs = True

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(7, GPIO.OUT)

        while self.readReg(REG_SYNCVALUE1) != 0xAA:
            self.writeReg(REG_SYNCVALUE1, 0xAA)
            
        while self.readReg(REG_SYNCVALUE1) != 0x55:
            self.writeReg(REG_SYNCVALUE1, 0x55)
        
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
            
        for key, value in CONFIG.items():
            self.writeReg(key, value)
            
        self.writeReg(REG_SYNCVALUE2, 210);
        
        self.rxMsg = []
        self.mode = False
        

    def select(self):
        GPIO.output(7, GPIO.LOW)

    def unselect(self):
        GPIO.output(7, GPIO.HIGH)

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
        self.mode = newMode
        self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | newMode)
        while (self.readReg(REG_IRQFLAGS1) & IRQ1_MODEREADY) == 0x00:
            pass
        
    def rfm69_receive (self):
        if self.mode != MODE_RECEIVE:
            self.rfm69_setMode(MODE_RECEIVE)
        else:
            if self.readReg(REG_IRQFLAGS2) & IRQ2_PAYLOADREADY:
                # FIFO access
                self.select()
                count = self.spi.xfer([REG_FIFO & 0x7F,0])[1]
                self.rxMsg = self.spi.xfer2([0 for i in range(0, count)])
                self.unselect()
                # only accept packets intended for us, or broadcasts
                # ... or any packet if we're the special catch-all node
                self.rssi = self.readReg(REG_RSSIVALUE)
                dest = self.rxMsg[0]
                if (dest & 0xC0) == self.parity:
                    destId = dest & 0x3F;
                    if destId == self.myId or destId == 0 or self.myId == 63:
                        return count;

        return -1
        

    def close(self):
        """Close socket."""
        pass

    def read(self):
        """Read data from RFM69 and process if complete line received.

        Return data as a list: [NodeID, val1, val2]

        """
        msg_len = self.rfm69_receive()
        if msg_len > 1:
            print (msg_len)
            print (self.rxMsg[1:])
            print (self.rssi)
            
            c = Cargo.new_cargo(rawdata='')
            c.nodeid = self.rxMsg[1]
            c.realdata = self.rxMsg[2:]
            c.rssi = -0.5*self.rssi
            return c

    def set(self, **kwargs):
        """

        """
        # include kwargs from parent
        super().set(**kwargs)
