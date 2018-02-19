import serial
import time
import Cargo
import re
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubTx3eInterfacer

Monitors the serial port for data

"""


class EmonHubTx3eInterfacer(EmonHubInterfacer):

    def __init__(self, name, com_port='', com_baud=9600):
        """Initialize interfacer

        com_port (string): path to COM port

        """

        # Initialization
        super(EmonHubTx3eInterfacer, self).__init__(name)

        self._settings.update({
            'nodename': "mynode",
            "datacode":False,
            "scale":1
        })
        
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
            s = False
            # raise EmonHubInterfacerInitError('Could not open COM port %s' % com_port)
        return s

    def read(self):
        """Read data from serial port and process if complete line received.

        Return data as a list: [val1, val2,...]
        
        """

        if not self._ser: return False
            
        # Read serial RX
        self._rx_buf = self._rx_buf + self._ser.readline()
        
        # If line incomplete, exit
        if '\r\n' not in self._rx_buf:
            return

        # Remove CR,LF
        f = self._rx_buf[:-2].strip()

        # Create a Payload object
        c = Cargo.new_cargo(rawdata=f)

        # Reset buffer
        self._rx_buf = ''

        # Parse the ESP format string
        values=[]
        names=[]

        for item in f.split(','):
            parts = item.split(':')
            if len(parts)==2:
                # check for alphanumeric input name
                if re.match('^[\w-]+$',parts[0]):
                    # check for numeric value
                    if parts[1].isdigit():
                        names.append(parts[0])
                        values.append(parts[1])
                    # log errors    
                    else: self._log.debug("input value is not numeric: "+parts[1])
                else: self._log.debug("invalid input name: "+parts[0])
                
        c.nodename = self._settings["nodename"]
        c.nodeid = self._settings["nodename"]
        c.realdata = values
        c.names = names
        
        if len(values)==0: 
            return False

        return c
        
    def set(self, **kwargs):
        for key,setting in self._settings.iteritems():
            if key in kwargs.keys():
                # replace default
                # self._log.debug(kwargs[key])
                self._settings[key] = kwargs[key]

