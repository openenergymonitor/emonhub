import time
import json
import datetime
import Cargo
from . import EmonHubSerialInterfacer as ehi

"""class EmonHubJeeInterfacer

Monitors the serial port for data from "Jee" type device

"""

class EmonHubJeeInterfacer(ehi.EmonHubSerialInterfacer):

    def __init__(self, name, com_port='/dev/ttyAMA0', com_baud=38400):
        """Initialize Interfacer

        com_port (string): path to COM port

        """

        # Initialization
        super().__init__(name, com_port, com_baud)

        # Display device firmware version and current settings
        self.info = ["", ""]
        if self._ser is not None:
            self._ser.write(b"v")
            time.sleep(2)  # FIXME sleep in initialiser smells
            self._rx_buf = self._rx_buf + self._ser.readline().decode()
            if '\r\n' in self._rx_buf:
                self._rx_buf = ""
                info = self._rx_buf + self._ser.readline().decode()[:-2]
                if info != "":
                    # Split the returned "info" string into firmware version & current settings
                    self.info[0] = info.strip().split(' ')[0]
                    self.info[1] = info.replace(str(self.info[0]), "")
                    self._log.info(self.name + " device firmware version: " + self.info[0])
                    self._log.info(self.name + " device current settings: " + str(self.info[1]))
                else:
                    # since "v" command only v11> recommend firmware update ?
                    #self._log.info(self.name + " device firmware is pre-version RFM12demo.11")
                    self._log.info(self.name + " device firmware version & configuration: not available")
            else:
                self._log.warning("Device communication error - check settings")
        self._rx_buf = ""
        self._ser.flushInput()

        # Initialize settings
        self._defaults.update({'pause': 'off', 'interval': 0, 'datacode': 'h'})

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)

        # Jee specific settings to be picked up as changes not defaults to initialise "Jee" device
        self._jee_settings = {'baseid': '15', 'frequency': '433', 'group': '210', 'quiet': 'True', 'calibration': '230V'}
        self._jee_prefix = {'baseid': 'i', 'frequency': '', 'group': 'g', 'quiet': 'q', 'calibration': 'p'}

        # Pre-load Jee settings only if info string available for checks
        if all(i in self.info[1] for i in (" i", " g", " @ ", " MHz")):
            self._settings.update(self._jee_settings)

    def add(self, cargo):
        """Append data to buffer.

        data (list): node and values (eg: '[node,val1,val2,...]')

        """

        #just send it
        txc = self._process_tx(cargo)
        self.send(txc)

    def read(self):
        """Read data from serial port and process if complete line received.

        Return data as a list: [NodeID, val1, val2]

        """

        # Read serial RX
        self._rx_buf = self._rx_buf + self._ser.readline().decode()

        # If line incomplete, exit
        if '\r\n' not in self._rx_buf:
            return

        # Remove CR,LF.
        f = self._rx_buf[:-2].strip()

        # Reset buffer
        self._rx_buf = ''

        if not f:
            return

        if f[0] == '\x01':
            #self._log.debug("Ignoring frame consisting of SOH character" + str(f))
            return

        if f[0] == '?':
            self._log.debug("Discarding RX frame 'unreliable content'" + str(f))
            return False

        # Discard information messages
        if '>' in f:
            if '->' in f:
                self._log.debug("confirmed sent packet size: " + str(f))
                return
            self._log.debug("acknowledged command: " + str(f))
            return

        # Record current device settings
        if all(i in f for i in (" i", " g", " @ ", " MHz")):
            self.info[1] = f
            self._log.debug("device settings updated: " + str(self.info[1]))
            return

        # Save raw packet to new cargo object
        c = Cargo.new_cargo(rawdata=f)

        # Convert single string to list of string values
        f = f.split(' ')

        # Strip leading 'OK' from frame if needed
        if f[0] == 'OK':
            f = f[1:]

        # Extract RSSI value if it's available
        if f[-1].startswith('(') and f[-1].endswith(')'):
            r = f[-1][1:-1]
            try:
                c.rssi = int(r)
            except ValueError:
                self._log.warning("Packet discarded as the RSSI format is invalid: " + str(f))
                return
            f = f[:-1]

        try:
            # Extract node id from frame
            c.nodeid = int(f[0]) + int(self._settings['nodeoffset'])
        except ValueError:
            return

        try:
            # Store data as a list of integer values
            c.realdata = [int(i) for i in f[1:]]
        except ValueError:
            return

        return c

    def set(self, **kwargs):
        """Send configuration parameters to the "Jee" type device through COM port

        **kwargs (dict): settings to be modified. Available settings are
        'baseid', 'frequency', 'group'. Example:
        {'baseid': '15', 'frequency': '4', 'group': '210'}

        """

        for key, setting in self._jee_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._jee_settings[key]
            # convert bools to ints
            if str(setting).capitalize() in ['True', 'False']:
                setting = int(setting.capitalize() == "True")
            # confirmation string always contains baseid, group and freq
            if all(i in self.info[1] for i in (" i", " g", " @ ", " MHz")):
                # If setting confirmed as already set, continue without changing
                if self._jee_prefix[key] + str(setting) in self.info[1].split():
                    continue
            elif key in self._settings and self._settings[key] == setting:
                continue
            if key == 'baseid' and 1 <= int(setting) <= 26:
                command = str(setting) + 'i'
            elif key == 'frequency' and setting in ['433', '868', '915']:
                command = setting[:1] + 'b'
            elif key == 'group' and 0 <= int(setting) <= 250:
                command = str(setting) + 'g'
            elif key == 'quiet' and 0 <= int(setting) < 2:
                command = str(setting) + 'q'
            elif key == 'calibration' and setting == '230V':
                command = '1p'
            elif key == 'calibration' and setting == '110V':
                command = '2p'

            else:
                self._log.warning("In interfacer set '%s' is not a valid setting for %s: %s" % (str(setting), self.name, key))
                continue
            self._settings[key] = setting
            self._log.info("Setting " + self.name + " %s: %s" % (key, setting) + " (" + command + ")")
            self._ser.write(command.encode())
            # Wait a sec between two settings
            time.sleep(1)

        # include kwargs from parent
        super().set(**kwargs)

    def action(self):
        """Actions that need to be done on a regular basis.

        This should be called in main loop by instantiater.

        """

        t = time.time()

        # Broadcast time to synchronize emonGLCD
        interval = int(self._settings['interval'])
        if interval:  # A value of 0 means don't do anything
            if t - self._interval_timestamp > interval:
                self._interval_timestamp = t
                now = datetime.datetime.now()
                self._log.debug(self.name + " broadcasting time: %02d:%02d" % (now.hour, now.minute))
                self._ser.write(b"00,%02d,%02d,00,s" % (now.hour, now.minute))

    def _process_post(self, databuffer):
        """Send data to server/broker or other output

        """

        for frame in databuffer:
            self._log.debug("node = " + str(frame[1]) + " node_data = " + json.dumps(frame))
            self.send(frame)
        return True

    def send(self, cargo):
        f = cargo
        cmd = "s"

        if self.getName() in f.encoded:
            data = f.encoded[self.getName()]
        else:
            data = f.realdata

        payload = ""
        for value in data:
            if not 0 < int(value) < 255:
                self._log.warning(self.name + " discarding Tx packet: values out of scope")
                return
            payload += str(int(value)) + ","

        payload += cmd

        self._log.debug(str(f.uri) + " sent TX packet: " + payload)
        self._ser.write(payload.encode())
