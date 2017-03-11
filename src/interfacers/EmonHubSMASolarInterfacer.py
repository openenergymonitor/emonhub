#!/usr/bin/python


# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

# This will background the task
# nohup python SMASolarMQTT.py 00:80:25:1D:AC:53 0000 1> SMASolarMQTT.log 2> SMASolarMQTT.log.error &

__author__ = 'Stuart Pittaway'

import time
import argparse
import sys
import traceback
import bluetooth
import datetime
from datetime import datetime
import serial
import time
import Cargo
from pydispatch import dispatcher
#import emonhub_interfacer as ehi
from pydispatch import dispatcher
from emonhub_interfacer import EmonHubInterfacer

from smalibrary import SMASolar_library


"""class EmonHubSMASolarInterfacer

Monitors a SMA Solar inverter over bluetooth

"""

class EmonHubSMASolarInterfacer(EmonHubInterfacer):

    def __init__(self, name, inverteraddress='', inverterpincode='0000'):
        """Initialize interfacer
        com_port (string): path to COM port
        """

        # Initialization
        super(EmonHubSMASolarInterfacer, self).__init__(name)

        self._inverteraddress=inverteraddress
        self._inverterpincode=inverterpincode
        self._port=1

        self._packet_send_counter = 0
        self._time_inverval = 5

        self._reset_duration_timer()

        # Open serial port
        self._login_inverter()

    def _reset_duration_timer(self):
        self._last_time_reading = time.time()

    def _login_inverter(self):
        """Log into the SMA solar inverter"""
        self._log.info("Log into the SMA solar inverter " + str(self._inverteraddress))

        self._btSocket = self._open_bluetooth(self._inverteraddress, self._port)


        #If bluetooth didnt work, exit here
        if self._btSocket is None:
            return

        self.InverterCodeArray = bytearray([0x5c, 0xaf, 0xf0, 0x1d, 0x50, 0x00]);

        # Dummy arrays
        self.AddressFFFFFFFF = bytearray([0xff, 0xff, 0xff, 0xff, 0xff, 0xff]);
        self.Address00000000 = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
        InverterPasswordArray = SMASolar_library.encodeInverterPassword(self._inverterpincode)

        #error_count = 0
        self._packet_send_counter = 0

        self.mylocalBTAddress = SMASolar_library.BTAddressToByteArray(self._btSocket.getsockname()[0], ":")
        self.mylocalBTAddress.reverse()

        SMASolar_library.initaliseSMAConnection(self._btSocket, self.mylocalBTAddress, self.AddressFFFFFFFF, self.InverterCodeArray,
                                                    self._packet_send_counter)

        # Logon to inverter
        pluspacket1 = SMASolar_library.SMANET2PlusPacket(0x0e, 0xa0, self._packet_send_counter, self.InverterCodeArray,
                                                             0x00,
                                                             0x01, 0x01)
        pluspacket1.pushRawByteArray(
            bytearray([0x80, 0x0C, 0x04, 0xFD, 0xFF, 0x07, 0x00, 0x00, 0x00, 0x84, 0x03, 0x00, 0x00]))
        pluspacket1.pushRawByteArray(
            SMASolar_library.floattobytearray(SMASolar_library.time.mktime(datetime.today().timetuple())))
        pluspacket1.pushRawByteArray(bytearray([0x00, 0x00, 0x00, 0x00]))
        pluspacket1.pushRawByteArray(InverterPasswordArray)

        send = SMASolar_library.SMABluetoothPacket(1, 1, 0x00, 0x01, 0x00, self.mylocalBTAddress, self.AddressFFFFFFFF)
        send.pushRawByteArray(pluspacket1.getBytesForSending())
        send.finish()
        send.sendPacket(self._btSocket)

        bluetoothbuffer = SMASolar_library.read_SMA_BT_Packet(self._btSocket, self._packet_send_counter, True,
                                                                  self.mylocalBTAddress)

        SMASolar_library.checkPacketReply(bluetoothbuffer, 0x0001)

        self._increment_packet_send_counter()

        if bluetoothbuffer.leveltwo.errorCode() > 0:
            raise Exception("Error code returned from inverter - during logon - wrong password?")

        inverterserialnumber = bluetoothbuffer.leveltwo.getFourByteLong(16)
        invName = SMASolar_library.getInverterName(self._btSocket, self._packet_send_counter, self.mylocalBTAddress,
                                                       self.InverterCodeArray,
                                                       self.AddressFFFFFFFF)
        self._increment_packet_send_counter()



    def close(self):
        """Close bluetooth port"""

        if self._btSocket is not None:
            self._log.info("Closing bluetooth port")
            self._btSocket.close()

    def _open_bluetooth(self, inverteraddress, port):
        """Open bluetooth

        inverteraddress (string): bluetooth address for inverter

        """
        try:
            self._log.info("Opening bluetooth address " + str(inverteraddress))
            btSocket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            # Connect
            btSocket.connect((inverteraddress, port))
            # Give BT 10 seconds to timeout so we don't hang and wait forever
            btSocket.settimeout(10)

        except bluetooth.btcommon.BluetoothError as err:
            self._log.error(err)
            self._log.error('Bluetooth error while connecting to %s' % inverteraddress)

        else:
            return btSocket

    def _increment_packet_send_counter(self):
        self._packet_send_counter += 1
        if self._packet_send_counter  > 200:
            self._packet_send_counter = 0

    def read(self):
        """Read data from inverter and process

        Return data as a list: [NodeID, val1, val2]

        """
        #Wait until we are ready to read from inverter
        duration_of_delay = time.time() - self._last_time_reading
        if (duration_of_delay< self._time_inverval):
            return

        self._reset_duration_timer()

        try:
            if self._btSocket is None:
                self._login_inverter()

            #If bluetooth didnt work, exit here
            if self._btSocket is None:
                return

            #Read the AC values from the inverter
            L2 = SMASolar_library.spotvalues_ac(self._btSocket, self._packet_send_counter, self.mylocalBTAddress, self.InverterCodeArray, self.AddressFFFFFFFF)
            self._increment_packet_send_counter()

            # Output 10 parameters for AC values
            # 0x4640 AC Output Phase 1
            # 0x4641 AC Output Phase 2
            # 0x4642 AC Output Phase 3
            # 0x4648 AC Line Voltage Phase 1
            # 0x4649 AC Line Voltage Phase 2
            # 0x464a AC Line Voltage Phase 3
            # 0x4650 AC Line Current Phase 1
            # 0x4651 AC Line Current Phase 2
            # 0x4652 AC Line Current Phase 3
            # 0x4657 AC Grid Frequency
            #payload = "{0},{1},{2},{3},{4},{5},{6},{7},{8},{9}".format(L2[1][1], L2[2][1], L2[3][1], L2[4][1],
            #                                                           L2[5][1],
            #                                                           L2[6][1], L2[7][1], L2[8][1], L2[9][1],
            #                                                           L2[10][1])

            #self._log.info(payload)
            payload = [L2[1][1], L2[2][1], L2[3][1], L2[4][1], L2[5][1], L2[6][1], L2[7][1], L2[8][1], L2[9][1], L2[10][1]]
            c = Cargo.new_cargo(realdata=payload)
            c.nodeid = 40
            #c.realdata = [int(i) for i in f[1:]]
            c.rssi=0
            #c.names=''

            return c

        except bluetooth.btcommon.BluetoothError as err1:
            self._log.error("Bluetooth Error")
            self._log.error(err1)
            #self._btSocket.close()
            self._btSocket = None

        except Exception as err2:
            self._log.error(err2)
            #self._btSocket.close()
            self._btSocket = None
