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
        
        self._settings_map = {'g':'group','i':'baseid','b':'frequency','d':'period','k0':'vcal','k1':'ical1','k2':'ical2','k3':'ical3','k4':'ical4','f':'acfreq','m1':'m1','t0':'t0'}
        self._settings_map_inv = dict(map(reversed, self._settings_map.items()))
        
        self._last_settings = {}

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)
        
        self._log.debug("Settings request")
        self._ser.write(b"l")

    def send_cal(self,cmd):
        self._ser.write((cmd+"\n").encode());

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
        
        # Handle debug
        if f[0] == '|':
            f = f[1:]
            self._log.debug(f)
            return
        
        # Handle settings
        fp = f.split(' ')
        if len(fp)==1:
            id = f[0]
        elif len(fp)>1:
            id = fp[0]
        
        # If the received key resides in the settings map (e.g b for frequency) 
        # check if the settings value matches the value sent from the hardware unit
        # if they do not match then attempt to fix the calibration value
        # Sending the value will trigger a further confirmation reply which is checked here again
        if id in self._settings_map:
            key = self._settings_map[id]
            if key in self._settings:
                cmd = "%s%s" % (id,self._settings[key])
                if f == cmd:
                    self._log.debug(key+" correct: "+cmd)
                else:
                    self.send_cal(cmd) 
                    self._log.debug(key+" updated: "+cmd)
            return
            
        # Save raw packet to new cargo object
        c = Cargo.new_cargo(rawdata=f)
        c.names = []
        c.realdata = []

        # Is the data in json format?
        if f[0]=="{" or f[0]=="[":
            try:
                json_data = json.loads(f)
                for key in json_data:
                    value = float(json_data[key])
                    c.names.append(key)
                    c.realdata.append(value)
                self._settings['datacode'] = False
            except ValueError as e:
               self._log.error("Invalid JSON: "+f)
               return
            if len(c.realdata) == 0:
                return 
            if self._settings["nodename"] != "":
                c.nodename = self._settings["nodename"]
                c.nodeid = self._settings["nodename"]
        
        # Is the data in key:value format?
        # power1:100,power2:200
        elif ":" in f and "," in f:
            for item in f.split(','):
                parts = item.split(':')
                if len(parts) == 2:
                    # check for alphanumeric input name
                    if re.match(r'^[\w-]+$', parts[0]):
                        # check for numeric value
                        try:
                            value = float(parts[1])
                            c.names.append(parts[0])
                            c.realdata.append(value)
                        except Exception:
                            self._log.debug("input value is not numeric: %s", parts[1])      
                    else:
                        self._log.debug("invalid input name: %s", parts[0])
            if len(c.realdata) == 0:
                return 
            if self._settings["nodename"] != "":
                c.nodename = self._settings["nodename"]
                c.nodeid = self._settings["nodename"]
            # Do not try and decode
            self._settings['datacode'] = False
            
        # Assume binary format
        # OK 5 0 0 0 0 0 0 134 91 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 (-0)
        else:
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

    def update_if_changed(self,key):
        # has the setting updated
        if key in self._last_settings:
            if self._last_settings[key] != self._settings[key]:
                cmd = self._settings_map_inv[key]+str(self._settings[key])
                self._log.debug(key+" updated "+cmd)
                self.send_cal(cmd)

    def set(self, **kwargs):
        
        for key, setting in self._settings.items():
            if key in kwargs:
                # replace default
                self._settings[key] = kwargs[key]
                
        if "group" in kwargs:
            self._settings["group"] = int(kwargs["group"])
            self.update_if_changed("group")
                
        if "frequency" in kwargs:
            self._settings["frequency"] = int(kwargs["frequency"])
            self.update_if_changed("frequency")
                    
        if "baseid" in kwargs:
            self._settings["baseid"] = int(kwargs["baseid"])
            self.update_if_changed("baseid")
            
        if "period" in kwargs:
            self._settings["period"] = float(kwargs["period"])
            self.update_if_changed("period")
                    
        if "vcal" in kwargs:
            self._settings["vcal"] = " %.2f 0.00" % float(kwargs["vcal"])
            self.update_if_changed("vcal")
            
        # up to 4 ical channels    
        for ch in range(1,4):
            key = "ical"+str(ch)
            if key in kwargs:
                if isinstance(kwargs[key],list):
                    if len(kwargs[key])==2:
                        self._settings[key] = " %.2f %.2f" % (float(kwargs[key][0]),float(kwargs[key][1]))
                else:
                    self._settings[key] = " %.2f 0.00" % float(kwargs[key])
                self.update_if_changed(key)
                    
        self._last_settings = self._settings.copy()

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
