#!/usr/bin/python
# EmonHubSMASolarInterfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

__author__ = 'Stuart Pittaway'

import time
import argparse
import sys
import string
import traceback
import bluetooth
import datetime
from datetime import datetime
import re
import serial
import time
import Cargo
from pydispatch import dispatcher

from pydispatch import dispatcher
from emonhub_interfacer import EmonHubInterfacer
from collections import namedtuple
from smalibrary import SMASolar_library


"""class EmonHubSMASolarInterfacer

Monitors a SMA Solar inverter over bluetooth

"""

class EmonHubSMASolarInterfacer(EmonHubInterfacer):

    def __init__(self, name, inverteraddress='', inverterpincode='0000', timeinverval=10, nodeid=29, readdcvalues=1):
        """Initialize interfacer
        com_port (string): path to COM port
        """

        # Initialization
        super(EmonHubSMASolarInterfacer, self).__init__(name)

        self._inverteraddress=inverteraddress
        self._inverterpincode=inverterpincode
        self._port=1
        self._nodeid=int(nodeid)
        self._readdcvalues=int(readdcvalues)

        self._packet_send_counter = 0
        self._Inverters = None
        #Duration in seconds
        self._time_inverval =  int(timeinverval)

        self._reset_duration_timer()
        self._reset_time_to_disconnect_timer();

        # Open serial port
        self._login_inverter()

        self._log.info("Reading from SMASolar every " + str(self._time_inverval) + " seconds")


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

        SMASolar_library.initaliseSMAConnection(self._btSocket, self.mylocalBTAddress, self.AddressFFFFFFFF, self.InverterCodeArray, self._packet_send_counter)

        # Logon to inverter
        pluspacket1 = SMASolar_library.SMANET2PlusPacket(0x0e, 0xa0, self._packet_send_counter, self.InverterCodeArray,  0x00,  0x01, 0x01)
        pluspacket1.pushRawByteArray( bytearray([0x0C, 0x04, 0xFD, 0xFF, 0x07, 0x00, 0x00, 0x00, 0x84, 0x03, 0x00, 0x00]))
        pluspacket1.pushRawByteArray( SMASolar_library.floattobytearray(SMASolar_library.time.mktime(datetime.today().timetuple())))
        pluspacket1.pushRawByteArray(bytearray([0x00, 0x00, 0x00, 0x00]))
        pluspacket1.pushRawByteArray(InverterPasswordArray)

        #pluspacket1.debugViewPacket()

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

        #TODO: We need to see what packets look like when we get multiple inverters talking to us
        inverterserialnumber = bluetoothbuffer.leveltwo.getFourByteLong(16)
        invName = SMASolar_library.getInverterName(self._btSocket, self._packet_send_counter, self.mylocalBTAddress,
                                                       self.InverterCodeArray,
                                                       self.AddressFFFFFFFF)
        self._increment_packet_send_counter()

        SMAInverterTuple = namedtuple('Inverter', 'SerialNumber Name NodeId NodeName')

        #valid_characters = string.ascii_letters + string.digits
        #allowed_characters =''.join(ch for ch in string.printable if ch in valid_characters)

        nodeName=re.sub(r'[^a-zA-Z0-9]','', invName)

        #Build list of inverters we communicate with
        self._Inverters = [ SMAInverterTuple( str(inverterserialnumber),invName,self._nodeid, nodeName) ]

        self._reset_time_to_disconnect_timer();

        self._log.info("Connected to SMA inverter named [" + self._Inverters[0].Name + "] with serial number ["+self._Inverters[0].SerialNumber+"] using NodeId="+str(self._Inverters[0].NodeId)+" and name="+self._Inverters[0].NodeName)


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
        """Increment the internal sequence number in SMA Packets"""
        self._packet_send_counter += 1

        #Prevent roll over
        if self._packet_send_counter >= 0x0FFF:
            self._packet_send_counter = 0

    def _reset_duration_timer(self):
        """Reset timer to current date/time"""
        self._last_time_reading = time.time()

    def _is_it_time(self):
        """Checks to see if the duration has expired

        Return true or false

        """
        duration_of_delay = time.time() - self._last_time_reading
        return (int(duration_of_delay) > self._time_inverval)

    def _is_it_time_to_disconnect(self):
        """Checks to see if 8 minutes has passed, if so, force a disconnect

        Return true or false

        """
        duration_of_delay = time.time() - self._last_time_auto_disconnect
        return (int(duration_of_delay) > 480)

    def _reset_time_to_disconnect_timer(self):
        """Reset timer to current date/time"""
        self._last_time_auto_disconnect = time.time()

    #Override base _process_rx code from emonhub_interfacer
    def _process_rx(self, rxc):

        if not rxc:
            return False

        self._log.debug(str(rxc.uri) + " Timestamp : " + str(rxc.timestamp))
        self._log.debug(str(rxc.uri) + " From Node : " + str(rxc.nodeid))
        if rxc.target:
            self._log.debug(str(rxc.uri) + " To Target : " + str(rxc.target))
        self._log.debug(str(rxc.uri) + "    Values : " + str(rxc.realdata))
        if rxc.rssi:
            self._log.debug(str(rxc.uri) + "      RSSI : " + str(rxc.rssi))

        return rxc

    #Override base read code from emonhub_interfacer
    def read(self):
        """Read data from inverter and process

        Return data as a list: [NodeID, val1, val2]

        """
        #Wait until we are ready to read from inverter
        if (self._is_it_time() == False):
            return

        self._reset_duration_timer()

        try:
            self._log.debug("Entering read try section")
            # Check we have a connection already, if not try and obtain one
            if self._btSocket is None:
                self._login_inverter()

            # If bluetooth didn't work, exit here
            if self._btSocket is None:
                return

            names= []
            values = []

            #Read the AC values from the inverter
            self._log.debug("Reading spotvalues AC")
            AC = SMASolar_library.spotvalues_ac(self._btSocket, self._packet_send_counter, self.mylocalBTAddress, self.InverterCodeArray, self.AddressFFFFFFFF)
            self._increment_packet_send_counter()

            #Yield and running hours
            self._log.debug("Reading spotvalues yield")
            Yield = SMASolar_library.spotvalues_yield(self._btSocket, self._packet_send_counter, self.mylocalBTAddress, self.InverterCodeArray, self.AddressFFFFFFFF)
            self._increment_packet_send_counter()
            AC.update(Yield)

            # DC power
            if (self._readdcvalues==1):
                self._log.debug("Reading spotvalues DC")
                DC = SMASolar_library.spotvalues_dcwatts(self._btSocket, self._packet_send_counter, self.mylocalBTAddress, self.InverterCodeArray, self.AddressFFFFFFFF)
                self._increment_packet_send_counter()
                AC.update(DC)

            self._log.debug("Extracting data")
            # Output values which match these keys - note some inverters wont return all data requested particularly DC string values
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
            # 0x251e DC Power Watts L3[1][1]
            # 0x2601 Total Yield Wh
            # 0x2622 Day Yield Wh
            # 0x462e Operating time (hours)
            # 0x462f Feed in time (hours)
            for key in [0x4640,0x4641,0x4642,0x4648,0x4649,0x464a,0x4650,0x4651,0x4652,0x4657,0x251e,0x2601,0x2622,0x462e,0x462f]:
                if key in AC:
                    names.append( AC[key].Label )
                    values.append( AC[key].Value )

            self._log.debug("Building cargo")
            c = Cargo.new_cargo()
            c.rawdata = None
            c.realdata = values
            c.names = names

            #TODO: We need to revisit this once we know how multiple inverters communicate with us
            c.nodeid = self._Inverters[0].NodeId
            c.nodename = self._Inverters[0].NodeName

            #TODO: We should be able to populate the rssi number from the bluetooth signal strength
            c.rssi=0

            #Inverter appears to kill our connection every 10 minutes, so disconnect after 8 minutes
            #to avoid errors in log files
            if (self._is_it_time_to_disconnect() == True):
                self._log.info("Disconnecting Bluetooth after timer expired")
                self._reset_time_to_disconnect_timer()
                self._btSocket.close()
                self._btSocket = None


            self._log.debug("Returning cargo")
            return c

        except bluetooth.btcommon.BluetoothError as err1:
            self._log.error("Bluetooth Error")
            self._log.error(err1)
            #self._btSocket.close()
            self._btSocket = None

        except Exception as err2:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self._log.error(err2)
            self._log.error(repr(traceback.format_exception(exc_type, exc_value,exc_traceback)))
            self._btSocket = None
