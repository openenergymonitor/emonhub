#!/usr/bin/python3
# EmonHubSMASolarInterfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

__author__ = 'Stuart Pittaway'
try:
    import bluetooth
    bluetooth_found = True
except ImportError:
    bluetooth_found = False

import time
import sys
import subprocess
import traceback
import re
import Cargo

from emonhub_interfacer import EmonHubInterfacer
from smalibrary import SMASolar_library

"""class EmonHubSMASolarInterfacer
Monitors a SMA Solar inverter over bluetooth
"""
class EmonHubSMASolarInterfacer(EmonHubInterfacer):

    def __init__(self, name, inverteraddress='', inverterpincode='0000', timeinverval=10, nodeid=29, packettrace=0):
        """Initialize interfacer"""

        # Initialization
        super().__init__(name)

        self._btSocket = None
        self._inverteraddress = inverteraddress
        self._inverterpincode = inverterpincode
        self._port = 1
        self._nodeid = int(nodeid)
        self._btRetrySleepTime = 10
        self.no_bluetooth_reported = False

        self._packettrace = bool(packettrace)

        # seems a hack & needs explaining why we need this
        self.MySerialNumber = bytearray([0x08, 0x00, 0xaa, 0xbb, 0xcc, 0xdd])

        self._reset_packet_send_counter()
        self._Inverters = {}
        #Duration in seconds
        self._time_inverval = int(timeinverval)
        self._InverterPasswordArray = SMASolar_library.encodeInverterPassword(self._inverterpincode)

        self._reset_duration_timer()
        self._reset_time_to_disconnect_timer()

        self._log.info("Reading from SMASolar every " + str(self._time_inverval) + " seconds")


    def _login_inverter(self):
        """Log into the SMA solar inverter"""

        self._log.info("Log into the SMA solar inverter " + str(self._inverteraddress))

        self._btSocket = self._open_bluetooth(self._inverteraddress, self._port)

        #If bluetooth didn't work, exit here
        if self._btSocket is None:
            return

        self._reset_packet_send_counter()

        self.mylocalBTAddress = SMASolar_library.BTAddressToByteArray(self._btSocket.getsockname()[0], ":")
        self.mylocalBTAddress.reverse()

        self._log.debug("initaliseSMAConnection")
        SMASolar_library.initaliseSMAConnection(self._btSocket, self.mylocalBTAddress, self.MySerialNumber, self._packet_send_counter)
        self._increment_packet_send_counter()
        self._increment_packet_send_counter()

        self._log.debug("logon")
        SMASolar_library.logon(self._btSocket, self.mylocalBTAddress, self.MySerialNumber, self._packet_send_counter, self._InverterPasswordArray)
        self._increment_packet_send_counter()

        self._reset_time_to_disconnect_timer()

        self._Inverters = {}

        #TODO: We need to see what packets look like when we get multiple inverters talking to us
        dictInverterData = SMASolar_library.getInverterDetails(self._btSocket, self._packet_send_counter, self.mylocalBTAddress, self.MySerialNumber)
        self._increment_packet_send_counter()

        #Returns dictionary like
        #{'inverterName': u'SN2120051742\x00\x00', 'serialNumber': 2120051742L, 'ClassName': 'SolarInverter', 'TypeName': 'SB 3000HF-30', 'susyid': 131L, 'Type': 9073L, 'Class': 8001L}

        self._log.debug(str(dictInverterData))

        #Clear rogue characters from name
        dictInverterData["inverterName"] = re.sub(r'[^a-zA-Z0-9]', '', dictInverterData["inverterName"])

        nodeName = dictInverterData["inverterName"]

        #Build list of inverters we communicate with
        self._Inverters[nodeName] = dictInverterData

        self._Inverters[nodeName]["NodeId"] = self._nodeid

        self._log.info("Connected to SMA inverter named [" + self._Inverters[nodeName]["inverterName"] + "] with serial number [" + str(self._Inverters[nodeName]["serialNumber"])
        + "] using NodeId=" + str(self._Inverters[nodeName]["NodeId"]) + ".  Model " + self._Inverters[nodeName]["TypeName"])

    def close(self):
        """Close bluetooth port"""

        if self._btSocket is not None:
            self._log.info("Closing bluetooth port")
            self._btSocket.close()

    def _open_bluetooth(self, inverteraddress, port):
        """Open bluetooth

        inverteraddress (string): bluetooth address for inverter

        """
        for retry_attempt in range(3):
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
                btSocket.close()
                errCode = eval(err[0])[0]
                if errCode == 16 or errCode == 115:
                    # We need to reset the bluetooth connection
                    self._reset_bluetooth()

            else:
                return btSocket

    def _reset_packet_send_counter(self):
        """Reset the internal sequence number in SMA Packets"""
        self._packet_send_counter = 0x0100

    def _increment_packet_send_counter(self):
        """Increment the internal sequence number in SMA Packets"""
        self._packet_send_counter += 1

        #Prevent roll over
        if self._packet_send_counter >= 0x0FFF:
            self._packet_send_counter = 0  # FIXME is this the same as "_reset_packet_send_counter" or not?

        #Appears that comms hangs on certain numbers
        #simple reset for now to resolve
        if self._packet_send_counter >= 0x0170:
            self._reset_packet_send_counter()

        self._log.debug("packet count = {0:04x}".format(self._packet_send_counter))

    def _reset_duration_timer(self):
        """Reset timer to current date/time"""
        self._last_time_reading = time.time()

    def _is_it_time(self):
        """Checks to see if the duration has expired
        Return true or false
        """

        duration_of_delay = time.time() - self._last_time_reading
        return int(duration_of_delay) > self._time_inverval

    def _is_it_time_to_disconnect(self):
        """Checks to see if 8 minutes has passed, if so, force a disconnect
        Return true or false
        """
        duration_of_delay = time.time() - self._last_time_auto_disconnect
        return int(duration_of_delay) > 480

    def _reset_time_to_disconnect_timer(self):
        """Reset timer to current date/time"""
        self._last_time_auto_disconnect = time.time()

    def _reset_bluetooth(self):
        subprocess.call(['sudo', 'systemctl', 'restart', 'bluetooth'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT)
        self._log.warning('Bluetooth processes restarted - not responding')

    #Override base _process_rx code from emonhub_interfacer
    def _process_rx(self, rxc):
        if not rxc:
            return False

        return rxc

    #Override base read code from emonhub_interfacer
    def read(self):
        """Read data from inverter and process"""
        if not bluetooth_found:
            if not self.no_bluetooth_reported:
                self._log.warning('Bluetooth not available...')
                self.no_bluetooth_reported = True
            return False

        #Wait until we are ready to read from inverter
        if not self._is_it_time():
            return

        self._reset_duration_timer()

        try:
            #self._log.debug("Entering read try section")

            # Check we have a connection already, if not try and obtain one
            if self._btSocket is None:
                self._login_inverter()

            # If bluetooth didn't work, exit here
            if self._btSocket is None:
                return

            readingsToMake = {
                "EnergyProduction": [0x54000200, 0x00260100, 0x002622FF],

                #This causes problems with some inverters
                #readingsToMake["SpotDCPower"] = [0x53800200, 0x00251E00, 0x00251EFF]

                "SpotACPower": [0x51000200, 0x00464000, 0x004642FF],
                "SpotACTotalPower": [0x51000200, 0x00263F00, 0x00263FFF],
                "SpotDCVoltage": [0x53800200, 0x00451F00, 0x004521FF],
                "SpotACVoltage": [0x51000200, 0x00464800, 0x004655FF],
                "SpotGridFrequency": [0x51000200, 0x00465700, 0x004657FF],
                "OperationTime": [0x54000200, 0x00462E00, 0x00462FFF],
                "InverterTemperature": [0x52000200, 0x00237700, 0x002377FF],
                #Not very useful for reporting
                #"MaxACPower": [0x51000200, 0x00411E00, 0x004120FF],
                #"MaxACPower2": [0x51000200, 0x00832A00, 0x00832AFF],
                #"GridRelayStatus": [0x51800200, 0x00416400, 0x004164FF],

                #Only useful on off grid battery systems
                #"ChargeStatus": [0x51000200, 0x00295A00, 0x00295AFF],
                #"BatteryInfo": [0x51000200, 0x00491E00, 0x00495DFF],
            }

            #Get first inverter in dictionary  # FIXME dicts aren't sorted, there is no "first"
            inverter = self._Inverters[list(self._Inverters.keys())[0]]
            self._log.debug("Reading from inverter " + inverter["inverterName"])

            #Loop through dictionary and take readings, building "output" dictionary as we go
            output = {}
            for reading, command in readingsToMake.items():
                data = SMASolar_library.request_data(
                    self._btSocket,
                    self._packet_send_counter,
                    self.mylocalBTAddress,
                    self.MySerialNumber,
                    command[0],
                    command[1],
                    command[2],
                    inverter["susyid"],
                    inverter["serialNumber"])

                self._increment_packet_send_counter()
                if data is not None:
                    output.update(SMASolar_library.extract_data(data))
                    if self._packettrace:
                        self._log.debug("Packet reply for " + reading + ". Packet from {0:04x}/{1:08x}".format(data.getTwoByte(14), data.getFourByteLong(16)))
                        self._log.debug(data.debugViewPacket())

            #self._log.debug("Building cargo")
            c = Cargo.new_cargo()
            c.rawdata = None
            #Sort the output to keep the keys in a consistent order
            c.names = []
            c.realdata = []
            for key in sorted(output):
                c.names.append(output[key].Label)
                c.realdata.append(output[key].Value)

            #TODO: We need to revisit this once we know how multiple inverters communicate with us
            c.nodeid = inverter["NodeId"]
            c.nodename = inverter["inverterName"]

            #TODO: We should be able to populate the rssi number from the bluetooth signal strength
            c.rssi = 0

            #Inverter appears to kill our connection every 10 minutes, so disconnect after 8 minutes
            #to avoid errors in log files
            if self._is_it_time_to_disconnect():
                self._log.info("Disconnecting Bluetooth after timer expired")
                SMASolar_library.logoff(self._btSocket, self._packet_send_counter, self.mylocalBTAddress, self.MySerialNumber)
                self._reset_time_to_disconnect_timer()
                self._btSocket.close()
                self._btSocket = None

            self._log.debug("Returning cargo")
            return c

        except bluetooth.btcommon.BluetoothError as err1:
            self._log.error("Bluetooth Error")
            self._log.error(err1)
            self._btSocket = None

        except Exception as err2:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self._log.error(err2)
            self._log.error(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            self._btSocket = None
