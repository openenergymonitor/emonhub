"""

  This code is released under the GNU Affero General Public License.
  
  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import serial
import time
import datetime
import logging
import socket
import select
import threading
import urllib2
import json
import uuid

import paho.mqtt.client as mqtt

import emonhub_coder as ehc

from pydispatch import dispatcher

"""class EmonHubInterfacer

Monitors a data source. 

This almost empty class is meant to be inherited by subclasses specific to
their data source.

"""


class EmonHubInterfacer(threading.Thread):

    def __init__(self, name):
        
        # Initialize logger
        self._log = logging.getLogger("EmonHub")

        # Initialise thread
        threading.Thread.__init__(self)
        self.setName(name)

        # Initialise settings
        self.init_settings = {}
        self._defaults = {'pause': 'off', 'interval': 0, 'datacode': '0',
                          'scale':'1', 'timestamped': False, 'targeted': False, 'nodeoffset' : '0','pub_channels':["ch1"],'sub_channels':["ch2"]}
        self._settings = {}

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)

        # Initialize interval timer's "started at" timestamp
        self._interval_timestamp = 0
        
        # create a stop
        self.stop = False

    def run(self):
        """
        Run the interfacer.
        Any regularly performed tasks actioned here along with passing received values

        """

        while not self.stop:
            # Read the input and process data if available
            rxc = self.read()
            # if 'pause' in self._settings and \
            #                 str.lower(self._settings['pause']) in ['all', 'in']:
            #     pass
            # else:
            if rxc:
                rxc = self._process_rx(rxc)
                if rxc:
                    for channel in self._settings["pub_channels"]:
                        dispatcher.send(channel, cargo=rxc)
                        self._log.debug(str(rxc.uri) + " Sent to channel' : " + str(channel))
                  
            # Don't loop to fast
            time.sleep(0.1)
            # Action reporter tasks
            self.action()
   
    # Subscribed channels entry                 
    def receiver(self, cargo):
        txc = self._process_tx(cargo)
        self.send(txc)
                            
    def read(self):
        """Read raw data from interface and pass for processing.
        Specific version to be created for each interfacer
        Returns an EmonHubCargo object
        """
        pass


    def send(self, cargo):
        """Send data from interface.
        Specific version to be created for each interfacer
        Accepts an EmonHubCargo object
        """
        pass


    def action(self):
        """Action any interfacer tasks,
        Specific version to be created for each interfacer
        """
        pass


    def _process_rx(self, cargo):
        """Process a frame of data

        f (string): 'NodeID val1 val2 ...'

        This function splits the string into numbers and check its validity.

        'NodeID val1 val2 ...' is the generic data format. If the source uses 
        a different format, override this method.
        
        Return data as a list: [NodeID, val1, val2]

        """

        # Log data
        self._log.debug(str(cargo.uri) + " NEW FRAME : " + cargo.rawdata)

        rxc = cargo
        decoded = []
        node = str(rxc.nodeid)
        datacode = True

        # Discard if data is non-existent
        if len(rxc.realdata) < 1:
            self._log.warning(str(cargo.uri) + " Discarded RX frame 'string too short' : " + str(rxc.realdata))
            return False

        # Discard if anything non-numerical found
        try:
            [float(val) for val in rxc.realdata]
        except Exception:
            self._log.warning(str(cargo.uri) + " Discarded RX frame 'non-numerical content' : " + str(rxc.realdata))
            return False
            
        # Discard if first value is not a valid node id
        # n = float(rxc.realdata[0])
        # if n % 1 != 0 or n < 0 or n > 31:
        #     self._log.warning(str(cargo.uri) + " Discarded RX frame 'node id outside scope' : " + str(rxc.realdata))
        #     return False

        # check if node is listed and has individual datacodes for each value
        if node in ehc.nodelist and 'datacodes' in ehc.nodelist[node]:
            if rxc.realdatacodes :
                datacodes = rxc.realdatacodes
            else:
                # fetch the string of datacodes
                datacodes = ehc.nodelist[node]['datacodes']
            # fetch a string of data sizes based on the string of datacodes
            datasizes = []
            for code in datacodes:
                datasizes.append(ehc.check_datacode(code))
            # Discard the frame & return 'False' if it doesn't match the summed datasizes
            if len(rxc.realdata) != sum(datasizes):
                self._log.warning(str(rxc.uri) + " RX data length: " + str(len(rxc.realdata)) +
                                  " is not valid for datacodes " + str(datacodes))
                return False
            else:
                # Determine the expected number of values to be decoded
                count = len(datacodes)
                # Set decoder to "Per value" decoding using datacode 'False' as flag
                datacode = False
        else:
            # if node is listed, but has only a single default datacode for all values
            if node in ehc.nodelist and 'datacode' in ehc.nodelist[node]:
                datacode = ehc.nodelist[node]['datacode']
            else:
            # when node not listed or has no datacode(s) use the interfacers default if specified
                datacode = self._settings['datacode']
            # Ensure only int 0 is passed not str 0
            if datacode == '0':
                datacode = 0
            # when no (default)datacode(s) specified, pass string values back as numerical values
            if not datacode:
                for val in rxc.realdata:
                    if float(val) % 1 != 0:
                        val = float(val)
                    else:
                        val = int(float(val))
                    decoded.append(val)
            # Discard frame if total size is not an exact multiple of the specified datacode size.
            elif len(rxc.realdata) % ehc.check_datacode(datacode) != 0:
                self._log.warning(str(rxc.uri) + " RX data length: " + str(len(rxc.realdata)) +
                                  " is not valid for datacode " + str(datacode))
                return False
            else:
            # Determine the number of values in the frame of the specified code & size
                count = len(rxc.realdata) / ehc.check_datacode(datacode)

        # Decode the string of data one value at a time into "decoded"
        if not decoded:
            bytepos = int(0)
            for i in range(0, count, 1):
                # Use single datacode unless datacode = False then use datacodes
                dc = datacode
                if not datacode:
                    dc = datacodes[i]
                # Determine the number of bytes to use for each value by it's datacode
                size = int(ehc.check_datacode(dc))
                try:
                    value = ehc.decode(dc, [int(v) for v in rxc.realdata[bytepos:bytepos+size]])
                except:
                    self._log.warning(str(rxc.uri) + " Unable to decode as values incorrect for datacode(s)")
                    return False
                bytepos += size
                decoded.append(value)

        # check if node is listed and has individual scales for each value
        if node in ehc.nodelist and 'scales' in ehc.nodelist[node]:
            scales = ehc.nodelist[node]['scales']
            # Discard the frame & return 'False' if it doesn't match the number of scales
            if len(decoded) != len(scales):
                self._log.warning(str(rxc.uri) + " Scales " + str(scales) + " for RX data : " + str(rxc.realdata) +
                                  " not suitable " )
                return False
            else:
                # Determine the expected number of values to be decoded

                # Set decoder to "Per value" scaling using scale 'False' as flag
                scale = False
        else:
            # if node is listed, but has only a single default scale for all values
            if node in ehc.nodelist and 'scale' in ehc.nodelist[node]:
                scale = ehc.nodelist[node]['scale']
            else:
            # when node not listed or has no scale(s) use the interfacers default if specified
                scale = self._settings['scale']


        if not scale == "1":
            for i in range(0, len(decoded), 1):
                x = scale
                if not scale:
                    x = scales[i]
                if x != "1":
                    val = decoded[i] * float(x)
                    if val % 1 == 0:
                        decoded[i] = int(val)

        rxc.realdata = decoded

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


    def _process_tx(self, cargo):
        """Prepare data for outgoing transmission.
        cargo is passed through this chain of processing to scale
        and then break the real values down into byte values,
        Uses the datacode data if available.

        DO NOT OVER-WRITE THE "REAL" VALUE DATA WITH ENCODED DATA !!!
        there may be other threads that need to use cargo.realdata to
        encode data for other targets.

        New "encoded" data is stored as a list of {interfacer:encoded-data} dicts.

        Returns cargo.
        """

        txc = cargo
        scaled = []
        encoded = []
        if txc.target:
            dest = str(txc.target)
        else:
            dest = str(txc.nodeid)

        # check if node is listed and has individual scales for each value
        if dest in ehc.nodelist and 'scales' in ehc.nodelist[dest]:
            scales = ehc.nodelist[dest]['scales']
            # Discard the frame & return 'False' if it doesn't match the number of scales
            if len(txc.realdata) != len(scales):
                self._log.warning(str(txc.uri) + " Scales " + str(scales) + " for RX data : " + str(txc.realdata) +
                                  " not suitable " )
                return False
            else:
                # Determine the expected number of values to be decoded

                # Set decoder to "Per value" scaling using scale 'False' as flag
                scale = False
        else:
            # if node is listed, but has only a single default scale for all values
            if dest in ehc.nodelist and 'scale' in ehc.nodelist[dest]:
                scale = ehc.nodelist[dest]['scale']
            else:
            # when node not listed or has no scale(s) use the interfacers default if specified
                scale = self._settings['scale']

        if scale == "1":
            scaled = txc.realdata
        else:
            for i in range(0, len(txc.realdata), 1):
                x = scale
                if not scale:
                    x = scales[i]
                if x == "1":
                    val = txc.realdata[i]
                else:
                    val = txc.realdata[i] / float(x)
                    if val % 1 == 0:
                        val = int(val)
                scaled.append(val)


        # check if node is listed and has individual datacodes for each value
        if (dest in ehc.nodelist and 'datacodes' in ehc.nodelist[dest]) or txc.realdatacodes:
            if txc.realdatacodes:
                datacodes = txc.realdatacodes
            else:
                # fetch the string of datacodes
                datacodes = ehc.nodelist[dest]['datacodes']
            # fetch a string of data sizes based on the string of datacodes
            datasizes = []
            for code in datacodes:
                datasizes.append(ehc.check_datacode(code))
            # Discard the frame & return 'False' if it doesn't match the summed datasizes
            if len(scaled) != len(datasizes):
                self._log.warning(str(txc.uri) + " TX datacodes: " + str(datacodes) +
                                  " are not valid for values " + str(scaled))
                return False
            else:
                # Determine the expected number of values to be decoded
                count = len(scaled)
                # Set decoder to "Per value" decoding using datacode 'False' as flag
                datacode = False
        else:
            # if node is listed, but has only a single default datacode for all values
            if dest in ehc.nodelist and 'datacode' in ehc.nodelist[dest]:
                datacode = ehc.nodelist[dest]['datacode']
            else:
            # when node not listed or has no datacode(s) use the interfacers default if specified
                datacode = self._settings['datacode']
            # Ensure only int 0 is passed not str 0
            if datacode == '0':
                datacode = 0
            # when no (default)datacode(s) specified, pass string values back as numerical values
            if not datacode:
                for val in scaled:
                    if float(val) % 1 != 0:
                        val = float(val)
                    else:
                        val = int(float(val))
                    encoded.append(val)
            # Discard frame if total size is not an exact multiple of the specified datacode size.
            # elif len(data) * ehc.check_datacode(datacode) != 0:
            #     self._log.warning(str(uri) + " TX data length: " + str(len(data)) +
            #                       " is not valid for datacode " + str(datacode))
            #     return False
            else:
            # Determine the number of values in the frame of the specified code & size
                count = len(scaled) #/ ehc.check_datacode(datacode)

        if not encoded:
            for i in range(0, count, 1):
                # Use single datacode unless datacode = False then use datacodes
                dc = datacode
                if not datacode:
                    dc = datacodes[i]
                
                for b in ehc.encode(dc,int(scaled[i])):
                    encoded.append(b)

        txc.encoded.update({self.getName():encoded})
        return txc

    def set(self, **kwargs):
        """Set configuration parameters.

        **kwargs (dict): settings to be sent. Example:
        {'setting_1': 'value_1', 'setting_2': 'value_2'}

        pause (string): pause status
            'pause' = all  pause Interfacer fully, nothing read, processed or posted.
            'pause' = in   pauses the input only, no input read performed
            'pause' = out  pauses output only, input is read, processed but not posted to buffer
            'pause' = off  pause is off and Interfacer is fully operational (default)
        
        """
    #def setall(self, **kwargs):

        for key, setting in self._defaults.iteritems():
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._defaults[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            #self.set(key, setting)

    #def set(self, key, setting):

            #if key == 'pause' and str(setting).lower() in ['all', 'in', 'out', 'off']:
            elif key == 'pause' and str(setting).lower() in ['all', 'in', 'out', 'off']:
                pass
            elif key == 'interval' and str(setting).isdigit():
                pass
            elif key == 'nodeoffset' and str(setting).isdigit():
                pass
            elif key == 'datacode' and str(setting) in ['0', 'b', 'B', 'h', 'H', 'L', 'l', 'f']:
                pass
            elif key == 'scale' and (int(setting == 1) or not (int(setting % 10))):
                pass
            elif key == 'timestamped' and str(setting).lower() in ['true', 'false']:
                pass
            elif key == 'targeted' and str(setting).lower() in ['true', 'false']:
                pass
            elif key == 'pub_channels':
                pass
            elif key == 'sub_channels':
                pass
            # elif key == 'rxchannels' and int(setting) >= 0 and int(setting) < 256:
            #     pass
            # elif key == 'txchannels' and int(setting) >= 0 and int(setting) < 256:
            #     pass
            else:
                self._log.warning("In interfacer set '%s' is not a valid setting for %s: %s" % (str(setting), self.name, key))
                continue
            self._settings[key] = setting
            self._log.debug("Setting " + self.name + " " + key + ": " + str(setting))

            # Is there a better place to put this?    
            for channel in self._settings["sub_channels"]:
                dispatcher.connect(self.receiver, channel)
                self._log.debug("Interfacer: Subscribed to channel' : " + str(channel))

"""class EmonhubSerialInterfacer

Monitors the serial port for data

"""


class EmonHubSerialInterfacer(EmonHubInterfacer):

    def __init__(self, name, com_port='', com_baud=9600):
        """Initialize interfacer

        com_port (string): path to COM port

        """

        # Initialization
        super(EmonHubSerialInterfacer, self).__init__(name)

        # Open serial port
        self._ser = self._open_serial_port(com_port, com_baud)
        
        # Initialize RX buffer
        self._rx_buf = ''

    def close(self):
        """Close serial port"""
        
        # Close serial port
        if self._ser is not None:
            self._log.debug("Closing serial port")
            self._ser.close()

    def _open_serial_port(self, com_port, com_baud):
        """Open serial port

        com_port (string): path to COM port

        """

        #if not int(com_baud) in [75, 110, 300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]:
        #    self._log.debug("Invalid 'com_baud': " + str(com_baud) + " | Default of 9600 used")
        #    com_baud = 9600

        try:
            s = serial.Serial(com_port, com_baud, timeout=0)
            self._log.debug("Opening serial port: " + str(com_port) + " @ "+ str(com_baud) + " bits/s")
        except serial.SerialException as e:
            self._log.error(e)
            raise EmonHubInterfacerInitError('Could not open COM port %s' %
                                           com_port)
        else:
            return s

    def read(self):
        """Read data from serial port and process if complete line received.

        Return data as a list: [NodeID, val1, val2]
        
        """

        # Read serial RX
        self._rx_buf = self._rx_buf + self._ser.readline()
        
        # If line incomplete, exit
        if '\r\n' not in self._rx_buf:
            return

        # Remove CR,LF
        f = self._rx_buf[:-2]

        # Reset buffer
        self._rx_buf = ''

        # Create a Payload object
        c = new_cargo(rawdata=f)

        f = f.split()

        if int(self._settings['nodeoffset']):
            c.nodeid = int(self._settings['nodeoffset'])
            c.realdata = f
        else:
            c.nodeid = int(f[0])
            c.realdata = f[1:]

        return c

"""class EmonHubJeeInterfacer

Monitors the serial port for data from "Jee" type device

"""


class EmonHubJeeInterfacer(EmonHubSerialInterfacer):

    def __init__(self, name, com_port='/dev/ttyAMA0', com_baud=0):
        """Initialize Interfacer

        com_port (string): path to COM port

        """

        # Initialization
        if com_baud != 0:
            super(EmonHubJeeInterfacer, self).__init__(name, com_port, com_baud)
        else:
            for com_baud in (57600, 9600):
                super(EmonHubJeeInterfacer, self).__init__(name, com_port, com_baud)
                self._ser.write("?")
                time.sleep(2)
                self._rx_buf = self._rx_buf + self._ser.readline()
                if '\r\n' in self._rx_buf or '\x00' in self._rx_buf:
                    self._ser.flushInput()
                    self._rx_buf=""
                    break
                elif self._ser is not None:
                    self._ser.close()
                continue

        
        # Display device firmware version and current settings
        self.info = ["",""]
        if self._ser is not None:
            self._ser.write("v")
            time.sleep(2)
            self._rx_buf = self._rx_buf + self._ser.readline()
            if '\r\n' in self._rx_buf:
                self._rx_buf=""
                info = self._rx_buf + self._ser.readline()[:-2]
                if info != "":
                    # Split the returned "info" string into firmware version & current settings
                    self.info[0] = info.strip().split(' ')[0]
                    self.info[1] = info.replace(str(self.info[0]), "")
                    self._log.info( self.name + " device firmware version: " + self.info[0])
                    self._log.info( self.name + " device current settings: " + str(self.info[1]))
                else:
                    # since "v" command only v11> recommend firmware update ?
                    #self._log.info( self.name + " device firmware is pre-version RFM12demo.11")
                    self._log.info( self.name + " device firmware version & configuration: not available")
            else:
                self._log.warning("Device communication error - check settings")
        self._rx_buf=""
        self._ser.flushInput()

        # Initialize settings
        self._defaults.update({'pause': 'off', 'interval': 0, 'datacode': 'h'})

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)

        # Jee specific settings to be picked up as changes not defaults to initialise "Jee" device
        self._jee_settings =  ({'baseid': '15', 'frequency': '433', 'group': '210', 'quiet': 'True'})
        self._jee_prefix = ({'baseid': 'i', 'frequency': '', 'group': 'g', 'quiet': 'q'})

        # Pre-load Jee settings only if info string available for checks
        if all(i in self.info[1] for i in (" i", " g", " @ ", " MHz")):
            self._settings.update(self._jee_settings)

    def read(self):
        """Read data from serial port and process if complete line received.

        Return data as a list: [NodeID, val1, val2]

        """

        # Read serial RX
        self._rx_buf = self._rx_buf + self._ser.readline()

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
        if " i" and " g" and " @ " and " MHz" in f:
            self.info[1] = f
            self._log.debug("device settings updated: " + str(self.info[1]))
            return

        # Save raw packet to new cargo object
        c = new_cargo(rawdata=f)

        # Convert single string to list of string values
        f = f.split(' ')

        # Strip leading 'OK' from frame if needed
        if f[0]=='OK':
            f = f[1:]

        # Extract RSSI value if it's available
        if str(f[-1])[0]=='(' and str(f[-1])[-1]==')':
            c.rssi = int(f[-1][1:-1])
            f = f[:-1]

        # Extract node id from frame
        c.nodeid = int(f[0]) + int(self._settings['nodeoffset'])

        # Store data as a list of integer values
        c.realdata = [int(i) for i in f[1:]]

        return c

        # # unix timestamp
        # t = round(time.time(), 2)
        #
        # # Process data frame
        # self._rxq.put(self._process_rx(f, t))

    def set(self, **kwargs):
        """Send configuration parameters to the "Jee" type device through COM port

        **kwargs (dict): settings to be modified. Available settings are
        'baseid', 'frequency', 'group'. Example:
        {'baseid': '15', 'frequency': '4', 'group': '210'}
        
        """

        for key, setting in self._jee_settings.iteritems():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._jee_settings[key]
            # convert bools to ints
            if str.capitalize(str(setting)) in ['True', 'False']:
                setting = int(setting == "True")
            # confirmation string always contains baseid, group anf freq
            if " i" and " g" and " @ " and " MHz" in self.info[1]:
                # If setting confirmed as already set, continue without changing
                if (self._jee_prefix[key] + str(setting)) in self.info[1].split():
                    continue
            elif key in self._settings and self._settings[key] == setting:
                continue
            if key == 'baseid' and int(setting) >=1 and int(setting) <=26:
                command = setting + 'i'
            elif key == 'frequency' and setting in ['433','868','915']:
                command = setting[:1] + 'b'
            elif key == 'group'and int(setting) >=0 and int(setting) <=212:
                command = setting + 'g'
            elif key == 'quiet' and int(setting) >=0 and int(setting) <2:
                command = str(setting) + 'q'
            else:
                self._log.warning("In interfacer set '%s' is not a valid setting for %s: %s" % (str(setting), self.name, key))
                continue
            self._settings[key] = setting
            self._log.info("Setting " + self.name + " %s: %s" % (key, setting) + " (" + command + ")")
            self._ser.write(command)
            # Wait a sec between two settings
            time.sleep(1)

        # include kwargs from parent
        super(EmonHubJeeInterfacer, self).set(**kwargs)

    def action(self):
        """Actions that need to be done on a regular basis. 
        
        This should be called in main loop by instantiater.
        
        """

        t = time.time()

        # Broadcast time to synchronize emonGLCD
        interval = int(self._settings['interval'])
        if interval:  # A value of 0 means don't do anything
            if t - self._interval_timestamp < interval:
                return
            now = datetime.datetime.now()
            hh = now.hour
            mm = now.minute
            # TODO EXPERIMENT with non-DST time for economy7
            #dst=now.hour - time.localtime()[-1]
            #self._log.debug(self.name + " non-DST adjusted time: %02d:%02d" % (dst, mm))
            self._interval_timestamp = t
            n = 0 + int(self._settings['nodeoffset'])
            packet = new_cargo( realdata = [0,hh,mm,0], target=n)
            self._log.debug(str(packet.uri) + " broadcast time: %02d:%02d" % (hh, mm))

            self.send(packet)
            #self.send_packet(packet)

    def send (self, cargo):
        """
        """
        #self._process_tx(self._txq.get())
        #self._rxq.put( self._process_rx(f, t))
        #dest = f[1]
        #packet = f[2:-1]
        #self.send_packet(packet, dest)
        # TODO amalgamate into 1 send

    #def send_packet(self, packet, id=0, cmd="s"):
        """

        """
        f = cargo
        cmd = "s"

        # # If the use of acks gets implemented
        # ack = False
        # if ack:
        #     cmd = "a"
        if self.getName() in f.encoded:
            data = f.encoded[self.getName()]
        else:
            data = f.realdata

        payload = ""
        for value in data:
            if int(value) < 0 or int(value) > 255:
                self._log.warning(self.name + " discarding Tx packet: values out of scope" )
                return
            payload += str(int(value))+","
        node = str(f.target - int(self._settings['nodeoffset']))
        if int(node) < 0 or int(node) > 31:
            self._log.warning(self.name + " discarding Tx packet: invalid node id" )
            return
        payload += node + cmd
        self._log.debug(str(f.uri) + " sent TX packet: " + payload)
        self._ser.write(payload)


"""class EmonHubSocketInterfacer

Monitors a socket for data, typically from ethernet link

"""


class EmonHubSocketInterfacer(EmonHubInterfacer):

    def __init__(self, name, port_nb=50011):
        """Initialize Interfacer

        port_nb (string): port number on which to open the socket

        """

        # Initialization
        super(EmonHubSocketInterfacer, self).__init__(name)

        # add an apikey setting
        self._skt_settings = {'apikey':""}
        self._settings.update(self._skt_settings)

        # Open socket
        self._socket = self._open_socket(port_nb)

        # Initialize RX buffer for socket
        self._sock_rx_buf = ''

    def _open_socket(self, port_nb):
        """Open a socket

        port_nb (string): port number on which to open the socket

        """

        self._log.debug('Opening socket on port %s', port_nb)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('', int(port_nb)))
            s.listen(1)
        except socket.error as e:
            self._log.error(e)
            raise EmonHubInterfacerInitError('Could not open port %s' %
                                           port_nb)
        else:
            return s

    def close(self):
        """Close socket."""
        
        # Close socket
        if self._socket is not None:
            self._log.debug('Closing socket')
            self._socket.close()

    def read(self):
        """Read data from socket and process if complete line received.

        Return data as a list: [NodeID, val1, val2]
        
        """

        # Check if data received
        ready_to_read, ready_to_write, in_error = \
            select.select([self._socket], [], [], 0)

        # If data received, add it to socket RX buffer
        if self._socket in ready_to_read:

            # Accept connection
            conn, addr = self._socket.accept()
            
            # Read data
            self._sock_rx_buf = self._sock_rx_buf + conn.recv(1024)
            
            # Close connection
            conn.close()

        # If there is at least one complete frame in the buffer
        if not '\r\n' in self._sock_rx_buf:
            return

        # Process and return first frame in buffer:
        f, self._sock_rx_buf = self._sock_rx_buf.split('\r\n', 1)

        # create a new cargo
        c = new_cargo(rawdata=f)

        # Split string into values
        f = f.split(' ')

        # If apikey is specified, 32chars and not all x's
        if 'apikey' in self._settings:
            if len(self._settings['apikey']) == 32 and self._settings['apikey'].lower != "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx":
                # Discard if apikey is not in received frame
                if not self._settings['apikey'] in f:
                    self._log.warning(str(c.uri) +" discarded frame: apikey not matched")
                    return
                # Otherwise remove apikey from frame
                f = [ v for v in f if self._settings['apikey'] not in v ]
                c.rawdata = ' '.join(f)
        else:
            pass


        # Extract timestamp value if one is expected or use 0
        timestamp = 0.0
        if self._settings['timestamped']:
            c.timestamp=f[0]
            f = f[1:]
        # Extract source's node id
        c.nodeid = int(f[0]) + int(self._settings['nodeoffset'])
        f=f[1:]
        # Extract the Target id if one is expected
        if self._settings['targeted']:
                #setting = str.capitalize(str(setting))
            c.target = int(f[0])
            f = f[1:]
        # Extract list of data values
        c.realdata = f#[1:]
        # Create a Payload object
        #f = new_cargo(data, node, timestamp, dest)

        return c


    def set(self, **kwargs):
        """

        """

        for key, setting in self._skt_settings.iteritems():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._skt_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'apikey':
                if str.lower(setting[:4]) == 'xxxx':
                    self._log.warning("Setting " + self.name + " apikey: obscured")
                    pass
                elif str.__len__(setting) == 32 :
                    self._log.info("Setting " + self.name + " apikey: set")
                    pass
                elif setting == "":
                    self._log.info("Setting " + self.name + " apikey: null")
                    pass
                else:
                    self._log.warning("Setting " + self.name + " apikey: invalid format")
                    continue
                self._settings[key] = setting
                # Next line will log apikey if uncommented (privacy ?)
                #self._log.debug(self.name + " apikey: " + str(setting))
                continue
            elif key == 'url' and setting[:4] == "http":
                self._log.info("Setting " + self.name + " url: " + setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super(EmonHubSocketInterfacer, self).set(**kwargs)





"""class EmonHubPacketGenInterfacer

Monitors a socket for data, typically from ethernet link

"""


class EmonHubPacketGenInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        """Initialize interfacer

        """

        # Initialization
        super(EmonHubPacketGenInterfacer, self).__init__(name)

        self._control_timestamp = 0
        self._control_interval = 5
        self._defaults.update({'interval': 5, 'datacode': 'b'})
        self._pg_settings = {'apikey': "", 'url': 'http://localhost/emoncms'}
        self._settings.update(self._pg_settings)

    def read(self):
        """Read data from the PacketGen emonCMS module.

        """
        t = time.time()

        if not (t - self._control_timestamp) > self._control_interval:
            return

        req = self._settings['url'] + \
              "/emoncms/packetgen/getpacket.json?apikey="

        try:
            packet = urllib2.urlopen(req + self._settings['apikey']).read()
        except:
            return

        # logged without apikey added for security
        self._log.info("requesting packet: " + req + "E-M-O-N-C-M-S-A-P-I-K-E-Y")

        try:
            packet = json.loads(packet)
        except ValueError:
            self._log.warning("no packet returned")
            return

        raw = ""
        target = 0
        values = []
        datacodes = []

        for v in packet:
            raw += str(v['value']) + " "
            values.append(int(v['value']))
            # PacketGen datatypes are 0, 1 or 2 for bytes, ints & bools
            # bools are currently read as bytes 0 & 1
            datacodes.append(['B', 'h', 'B'][v['type']])

        c = new_cargo(rawdata=raw)

        # Extract the Target id if one is expected
        if self._settings['targeted']:
                #setting = str.capitalize(str(setting))
            c.target = int(values[0])
            values = values[1:]
            datacodes = datacodes[1:]

        c.realdata = values
        c.realdatacodes = datacodes

        self._control_timestamp = t
        c.timestamp = t

        # Return a Payload object
        #x = new_cargo(realdata=data)
        #x.realdatacodes = datacodes
        return c


    def action(self):
        """Actions that need to be done on a regular basis.

        This should be called in main loop by instantiater.

        """

        t = time.time()

        # Keep in touch with PacketGen and update refresh time
        interval = int(self._settings['interval'])
        if interval:  # A value of 0 means don't do anything
            if not (t - self._interval_timestamp) > interval:
                return

            try:
                 z = urllib2.urlopen(self._settings['url'] +
                                     "/emoncms/packetgen/getinterval.json?apikey="
                                     + self._settings['apikey']).read()
                 i = int(z[1:-1])
            except:
                self._log.info("request interval not returned")
                return

            if self._control_interval != i:
                self._control_interval = i
                self._log.info("request interval set to: " + str(i) + " seconds")

            self._interval_timestamp = t

        return

    def set(self, **kwargs):
        """

        """

        for key, setting in self._pg_settings.iteritems():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._pg_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'apikey':
                if str.lower(setting[:4]) == 'xxxx':
                    self._log.warning("Setting " + self.name + " apikey: obscured")
                    pass
                elif str.__len__(setting) == 32 :
                    self._log.info("Setting " + self.name + " apikey: set")
                    pass
                elif setting == "":
                    self._log.info("Setting " + self.name + " apikey: null")
                    pass
                else:
                    self._log.warning("Setting " + self.name + " apikey: invalid format")
                    continue
                self._settings[key] = setting
                # Next line will log apikey if uncommented (privacy ?)
                #self._log.debug(self.name + " apikey: " + str(setting))
                continue
            elif key == 'url' and setting[:4] == "http":
                self._log.info("Setting " + self.name + " url: " + setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super(EmonHubPacketGenInterfacer, self).set(**kwargs)


"""class EmonHubMqttGenInterfacer


"""


class EmonHubMqttInterfacer(EmonHubInterfacer):

    def __init__(self, name, mqtt_host="127.0.0.1", mqtt_port=1883):
        # Initialization
        super(EmonHubMqttInterfacer, self).__init__(name)
        
        self._log.info(str(name)+" Init mqtt_host="+str(mqtt_host)+" mqtt_port="+str(mqtt_port))
        self._name = name
        self._host = mqtt_host
        self._port = mqtt_port
        self._connected = False
        
        self._settings = {
            'sub_channels':['ch1'],
            'pub_channels':['ch2'],
            'basetopic': 'emonhub/'
        };

        self._mqttc = mqtt.Client()
        self._mqttc.on_connect = self.on_connect
        self._mqttc.on_message = self.on_message
        self._mqttc.on_subscribe = self.on_subscribe
        

    def action(self):
        if not self._connected:
            self._log.info("Connecting to MQTT Server")
            self._mqttc.connect(self._host, self._port, 60)
        self._mqttc.loop()
        
    def on_connect(self, client, userdata, rc):
        
        connack_string = {0:'Connection successful',
                          1:'Connection refused - incorrect protocol version',
                          2:'Connection refused - invalid client identifier',
                          3:'Connection refused - server unavailable',
                          4:'Connection refused - bad username or password',
                          5:'Connection refused - not authorised'}

        if rc:
            self._log.warning(connack_string[rc])
        else:
            self._log.info("connection status: "+connack_string[rc])
            self._connected = True
            # Subscribe to MQTT topics
            self._mqttc.subscribe(self._settings["basetopic"]+"tx/#")
            
        self._log.debug("CONACK => Return code: "+str(rc))

    def on_subscribe(self, mqttc, obj, mid, granted_qos):
        self._log.info("on_subscribe")

    def on_message(self, client, userdata, msg):
        topic_parts = msg.topic.split("/")
        
        if topic_parts[0] == self._settings["basetopic"][:-1]:
            if topic_parts[1] == "tx":
                if topic_parts[3] == "values":
                    nodeid = int(topic_parts[2])
                    
                    payload = str(nodeid)+","+msg.payload
                    realdata = payload.split(",")
                    self._log.debug("Nodeid: "+str(nodeid)+" values: "+msg.payload)

                    rxc = new_cargo(realdata=realdata)
                    rxc.nodeid = nodeid

                    if rxc:
                        rxc = self._process_tx(rxc)
                        if rxc:
                            for channel in self._settings["pub_channels"]:
                                dispatcher.send(channel, cargo=rxc)
                                self._log.debug(str(rxc.uri) + " Sent to channel' : " + str(channel))

    def receiver(self, cargo):
        if self._connected:
            topic = self._settings["basetopic"]+"rx/"+str(cargo.nodeid)+"/values"
            payload = ",".join(map(str,cargo.realdata))
            
            self._log.info("Publishing: "+topic+" "+payload)
            self._mqttc.publish(topic, payload=payload, qos=0, retain=False)
    
    def set(self, **kwargs):
        for key,setting in self._settings.iteritems():
            if key in kwargs.keys():
                # replace default
                self._settings[key] = kwargs[key]
        
        # Subscribe to internal channels   
        for channel in self._settings["sub_channels"]:
            dispatcher.connect(self.receiver, channel)
            self._log.debug(self._name+" Subscribed to channel' : " + str(channel))


"""class EmonHubInterfacerInitError

Raise this when init fails.

"""
class EmonHubInterfacerInitError(Exception):
    pass




class EmonHubCargo(object):
    uri = 0
    timestamp = 0.0
    target = 0
    nodeid = 0
    realdata = []
    rssi = 0

    # The class "constructor" - It's actually an initializer
    def __init__(self, timestamp, target, nodeid, realdata, rssi, rawdata):
        EmonHubCargo.uri += 1
        self.uri = EmonHubCargo.uri
        self.timestamp = float(timestamp)
        self.target = int(target)
        self.nodeid = int(nodeid)
        self.realdata = realdata
        self.rssi = int(rssi)

        self.datacodes = []
        self.datacode = ""
        self.scale = 0
        self.scales = []
        self.rawdata = rawdata
        self.encoded = {}
        self.realdatacodes = []

def new_cargo(rawdata="", realdata=[], nodeid=0, timestamp=0.0, target=0, rssi=0.0):
    """

    :rtype : object
    """

    if not timestamp:
        timestamp = time.time()
    cargo = EmonHubCargo(timestamp, target, nodeid, realdata, rssi, rawdata)
    return cargo
