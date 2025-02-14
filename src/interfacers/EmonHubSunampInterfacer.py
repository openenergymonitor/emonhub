import time
import json
import datetime
import Cargo
import re

from . import EmonHubSerialInterfacer as ehi

"""class EmonHubSunampInterfacer

Monitors the serial port for data from 'Serial Format 2' type devices

"""

class EmonHubSunampInterfacer(ehi.EmonHubSerialInterfacer):

    def __init__(self, name, com_port='/dev/ttyUSB0', com_baud=115200):
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
        self._defaults.update({'pause': 'off', 'interval': 0, 'nodename': name})

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)
        
        self._com_port = com_port
        self._com_baud = com_baud
        self._last_connection_attempt = time.time()


    def read(self):

        if not self._ser:
            if (time.time()-self._last_connection_attempt)>=10:
                self._last_connection_attempt = time.time()
                self._ser = self._open_serial_port(self._com_port, self._com_baud)
        
        if not self._ser:
            return

        # Read serial RX
        try:
            ser_data = self._ser.readline()
            self._rx_buf = self._rx_buf + ser_data.decode()
        except UnicodeDecodeError:
            return
        except Exception as e:
            self._log.error(e)
            self._ser = False

        # If line incomplete, exit
        if '\n' not in self._rx_buf:
            return

        # Remove CR,LF.
        f = self._rx_buf[:-1].strip()

        # Reset buffer
        self._rx_buf = ''

        if not f:
            return

        if f[0] == '\x01':
            return

        c = Cargo.new_cargo(rawdata=f)
        c.names = []
        c.realdata = []

        print()

        # Fetch default nodename from settings
        if self._settings["nodename"] != "":
            c.nodename = self._settings["nodename"]
            c.nodeid = self._settings["nodename"]


        # Example sunamp data:
        # e V12.2.0 4/1/0 F:0, TS: 81.78, 27.08, 23.65, err: 0, SOHT: 0, ELCD: 1, extD: 0, SOC: 0, CHG: 1, DC_R1: 1, DC_R2: 0, RLY: 1, RLY1: 0, CL: 1, L3: 0, DSR: 0
        
        # check that first character is 'e'
        if f[0] != 'e':
            return False

        # split the string into parts
        csv_parts = f.split(',')

        # first part beyond e contains, version number, something else and then F:0
        first = csv_parts[0].split(' ')

        # get version
        version = first[1]

        # add version to the list of names
        c.names.append('version')
        # only allow 0-9 characters in version
        c.realdata.append(int(re.sub(r'[^\d]', '', version)))

        unknown = first[2]
        c.names.append('unknown')
        c.realdata.append(int(re.sub(r'[^\d]', '', unknown)))

        # check if F:
        if 'F:' in first[3]:
            # add this to the list of names
            c.names.append('F')
            # add the value to the list of realdata
            c.realdata.append(float(first[3].split(':')[1]))

        # The first 

        key = ""
        key_index = 1

        for kv_str in csv_parts[1:]:
            if ":" in kv_str:
                kv = kv_str.split(':')
                key = kv[0]
                value = kv[1]
                key_index = 1
            else: 
                value = kv_str
                key_index += 1

            try:
                # add the key to the list of names
                if key_index == 1:
                    c.names.append(key)
                else:
                    c.names.append(key+str(key_index))
                # add the value to the list of realdata
                c.realdata.append(float(value))
            except Exception as e:
                return False
    
        self._log.debug("names: %s", c.names)

        if len(c.realdata) == 0:
            return False
        else:
            return c
            

    def set(self, **kwargs):
        for key, setting in self._settings.items():
            if key in kwargs:
                self._settings[key] = kwargs[key]