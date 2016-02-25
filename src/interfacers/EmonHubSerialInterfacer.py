import serial
import time
import Cargo
from pydispatch import dispatcher
import emonhub_interfacer as ehi

"""class EmonhubSerialInterfacer

Monitors the serial port for data

"""


class EmonHubSerialInterfacer(ehi.EmonHubInterfacer):

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
            s = serial.Serial(com_port, com_baud, timeout=10)
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
        try:
            self._rx_buf = self._rx_buf + self._ser.readline()
        except Exception,e:
            self._log.error(e)
            self._rx_buf = ""
            
        
        # If line incomplete, exit
        if '\r\n' not in self._rx_buf:
            return

        # Remove CR,LF
        self._log.debug("RAW DATA %s" %str(self._rx_buf))
        #print "RAW DATA %s"%self._rx_buf

        #remove any trailing null or whitespace characters
        f = self._rx_buf[:-2].strip()
        f = f.replace('\x00',' ')

        #print "CLEAN DATA %s"%self._rx_buf
        # Reset buffer
        self._rx_buf = ''
        #self._log.debug("CLEAN DATA %" %str(self._rx_buf))
        

        # Create a Payload object
        c = Cargo.new_cargo(rawdata=f)

        f = f.split()	
	if f:
	        if int(self._settings['nodeoffset']):
                    c.nodeid = int(self._settings['nodeoffset'])
                    c.realdata = f
                else:
                   try:
                       c.nodeid = int(f[0])
                       c.realdata = f[1:]
                   except Exception,e:
                       self._log.error("unable to decode packet skipping" +str(e))
                       pass
                       


        return c

