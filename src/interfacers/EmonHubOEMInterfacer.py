import time
import json
import datetime
import Cargo
import re
from . import EmonHubSerialInterfacer as ehi

"""class EmonHubOEMInterfacer

Monitors the serial port for data from 'Serial Format 2' type devices

"""

class EmonHubOEMInterfacer(ehi.EmonHubSerialInterfacer):

    def __init__(self, name, com_port='/dev/ttyAMA0', com_baud=38400):
        """Initialize Interfacer

        com_port (string): path to COM port

        """

        # Initialization
        super().__init__(name, com_port, com_baud)

        # Display device firmware version and current settings
        self.info = ["", ""]

        self._rx_buf = ""
        # self._ser.flushInput()

        # Initialize settings
        self._defaults.update({'pause': 'off', 'interval': 0, 'datacode': 'h', 'nodename': 'test'})

        self._config_map = {'g': 'group',
                            'i': 'baseid',
                            'b': 'frequency',
                            'd': 'period',
                            'k0': 'vcal',
                            'k1': 'ical1',
                            'k2': 'ical2',
                            'k3': 'ical3',
                            'k4': 'ical4',
                            'f': 'acfreq',
                            'm1': 'm1',
                            't0': 't0',
                            'a': 'Vrms',
                           }
        self._config_map_inv = dict(map(reversed, self._config_map.items()))

        self._last_config = {}
        self._config = {}

        self._config_format = "new"

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)

        self._first_data_packet_received = False


    def add(self, cargo):
        """Append data to buffer.

        data (list): node and values (eg: '[node,val1,val2,...]')

        """

        #just send it
        txc = self._process_tx(cargo)
        self.send(txc)


    def pre_process_data_format(self, f):
        """Pre process data

        checks for valid data format, returns pre-processed data

        """

        c = Cargo.new_cargo(rawdata=f)
        c.names = []
        c.realdata = []

        # Fetch default nodename from settings
        if self._settings["nodename"] != "":
            c.nodename = self._settings["nodename"]
            c.nodeid = self._settings["nodename"]

        # -------------------------------------------------------------------
        # JSON FORMAT e.g {"power1":100,"power2":200}
        # -------------------------------------------------------------------
        # Start with a quick check for the expected starting character
        if f[0] == "{" or f[0] == "[":
            try:                                        # Attempt to decode json
                json_data = json.loads(f)
                for name in json_data:
                    if re.match(r'^[\w-]+$', name):     # only alpha-numeric input names
                        c.realdata.append(float(json_data[name])) # check that value is numeric
                        c.names.append(name)
                    # else:
                    #     self._log.debug("invalid input name: %s" % kv[0])
            except ValueError as e:
                # self._log.debug("Invalid JSON: "+f)
                return False
            self._settings['datacode'] = False          # Disable further attempt at data decode
        # -------------------------------------------------------------------
        # KEY:VALUE FORMAT e.g power1:100,power2:200
        # -------------------------------------------------------------------
        elif ":" in f:
            for kv_str in f.split(','):
                kv = kv_str.split(':')
                if len(kv) == 2:
                    if re.match(r'^[\w-]+$', kv[0]):
                        if len(kv[1]) > 0:
                            try:
                                c.realdata.append(float(kv[1]))
                                c.names.append(kv[0])
                            except Exception:
                                # self._log.debug("input value is not numeric: %s" % kv[1])
                                return False
                    else:
                        # self._log.debug("invalid input name: %s" % kv[0])
                        return False
            self._settings['datacode'] = False          # Disable further attempt at data decode
        # -------------------------------------------------------------------
        # BINARY FORMAT e.g OK 5 0 0 0 0 (-0)'
        # -------------------------------------------------------------------
        elif " " in f:
            # Split string by space
            ssv = f.split(' ')
            # Strip leading 'OK' from frame if needed
            if ssv[0] == 'OK':
                ssv = ssv[1:]
            # Extract RSSI value if it's available
            if ssv[-1].startswith('(') and ssv[-1].endswith(')'):
                r = ssv[-1][1:-1]
                try:
                    c.rssi = int(r)
                except ValueError:
                    #self._log.warning("Packet discarded as the RSSI format is invalid: " + str(f))
                    return False
                ssv = ssv[:-1]
            # Extract node id from frame
            try:
                c.nodeid = int(ssv[0]) + int(self._settings['nodeoffset'])
            except ValueError:
                return False
            # Store data as a list of integer values
            try:
                c.realdata = [int(i) for i in ssv[1:]]
            except ValueError:
                return False

        if len(c.realdata) == 0:
            return False

        # If we are here the data is valid and processed
        return c

    def read(self):
        """Read data from serial port and process if complete line received.

        Return data as a list: [NodeID, val1, val2]

        """

        if not self._ser:
            return

        # Read serial RX
        try:
            self._rx_buf = self._rx_buf + self._ser.readline().decode()
        except UnicodeDecodeError:
            return

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

        # Check for valid data format (json, keyval, binary) and pre-process into cargo if valid
        c = self.pre_process_data_format(f)

        # If valid data
        if c:
            # Discard first data packet and send configuration
            if not self._first_data_packet_received:
                self._first_data_packet_received = True
                self.update_all()
                return
            else:
                return c

        self._log.debug(f)

        # Enable online calibration for EmonTx
        if f == "'+++' then [Enter] for config mode":
            # special silent version that does not print helptext
            self._ser.write("++s\r\n".encode())
            time.sleep(0.1)
            self._ser.write("k\r\n".encode())
            time.sleep(0.1)
            self._ser.write("x\r\n".encode())

        """
        # Handle config
        fp = f.split(' ')
        if len(fp)==1:
            id = f[0]
        elif len(fp)>1:
            id = fp[0]

        # If the received key resides in the config map (e.g b for frequency)
        # check if the config value matches the value sent from the hardware unit
        # if they do not match then attempt to fix the calibration value
        # Sending the value will trigger a further confirmation reply which is checked here again
        if id in self._config_map:
            key = self._config_map[id]
            if key in self._config:
                cmd = "%s%s" % (id,self._config[key])
                if f == cmd:
                    self._log.debug(key+" correct: "+cmd)
                else:
                    self.send_cal(key,cmd)
                    self._log.debug(key+" updated: "+cmd)
            return
        """

        return

    def send_cmd(self, cmd):
        self._ser.write((cmd+"\n").encode())
        # Wait for reply
        rx_buf = ""
        start = time.time()
        while time.time() - start < 1.0:
            rx_buf = rx_buf + self._ser.readline().decode()
            if '\r\n' in rx_buf:
                return rx_buf.strip()
        return False

    def check_config_format(self):
        self._config_format = "new"
        if self.send_cmd("4v"):
            self._config_format = "old"
        self._log.debug("Config format: " + self._config_format)
        if self._config_format == "new":
            time.sleep(2.1)

    def send_config(self, key, cmd):
        reply = self.send_cmd(cmd)
        if reply:
            self._log.debug("CONFIG SET:" + key.ljust(12, ' ') + " cmd:" + cmd.ljust(15, ' ') + " reply:" + reply)
        else:
            self._log.error("CONFIG FAIL: " + key + " cmd: " + cmd + " (no reply)")


    def update_all(self):
        # Send all available configuration
        self._log.debug("---------------------------------------------------------------------")
        self.check_config_format()
        for key in self._config:
            if self._config_format == "new":
                cmd = self._config_map_inv[key]+str(self._config[key])
            else:
                cmd = str(self._config[key])+self._config_map_inv[key]
            self.send_config(key, cmd)
        self._log.debug("---------------------------------------------------------------------")

    def update_if_changed(self, key):
        # has the setting updated
        if key in self._last_config:
            if self._last_config[key] != self._config[key]:
                if self._config_format == "new":
                    cmd = self._config_map_inv[key]+str(self._config[key])
                else:
                    cmd = str(self._config[key])+self._config_map_inv[key]
                self.send_config(key, cmd)

    def set(self, **kwargs):

        for key, setting in self._settings.items():
            if key in kwargs:
                # replace default
                self._settings[key] = kwargs[key]

        if "group" in kwargs:
            self._config["group"] = int(kwargs["group"])
            self.update_if_changed("group")

        if "frequency" in kwargs:
            self._config["frequency"] = int(kwargs["frequency"])
            self.update_if_changed("frequency")

        if "baseid" in kwargs:
            self._config["baseid"] = int(kwargs["baseid"])
            self.update_if_changed("baseid")

        if "period" in kwargs:
            self._config["period"] = float(kwargs["period"])
            self.update_if_changed("period")

        if "vcal" in kwargs:
            self._config["vcal"] = " %.2f 0.00" % float(kwargs["vcal"])
            self.update_if_changed("vcal")

        # up to 4 ical channels
        for ch in range(1, 5):
            key = "ical" + str(ch)
            if key in kwargs:
                if isinstance(kwargs[key], list):
                    if len(kwargs[key]) == 2:
                        self._config[key] = " %.2f %.2f" % (float(kwargs[key][0]), float(kwargs[key][1]))
                else:
                    self._config[key] = " %.2f 0.00" % float(kwargs[key])
                self.update_if_changed(key)

        #if "cmd" in kwargs:
        #    self._log.debug(kwargs["cmd"])


        self._last_config = self._config.copy()

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

        payload = "T"
        for value in data:
            if not 0 < int(value) < 255:
                self._log.warning(self.name + " discarding Tx packet: values out of scope")
                return
            payload += str(int(value)) + ","

        # payload += cmd

        self._log.debug(str(f.uri) + " sent TX packet: " + payload)
        self._ser.write(payload.encode())
