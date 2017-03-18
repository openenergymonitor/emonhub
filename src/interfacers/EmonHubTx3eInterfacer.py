import serial
import time
import Cargo
from pydispatch import dispatcher
import emonhub_coder as ehc
import emonhub_interfacer as ehi

"""class EmonHubTx3eInterfacer

Monitors the serial port for data

"""


class EmonHubTx3eInterfacer(ehi.EmonHubInterfacer):

    def __init__(self, name, com_port='', com_baud=9600):
        """Initialize interfacer

        com_port (string): path to COM port

        """

        # Initialization
        super(EmonHubTx3eInterfacer, self).__init__(name)

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

        Return data as a list: [val1, val2,...]
        
        """

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
        payload=''
        if f.startswith('ct1:'):
          for item in f.split(',')[:]:
            payload+=' '+item.split(':')[1]
        f=payload

        if int(self._settings['nodeoffset']):
            c.nodeid = int(self._settings['nodeoffset'])
            c.realdata = f
        else:
            c.nodeid = int(f[0])
            c.realdata = f[1:]

        return c

    def _process_rx(self, cargo):
        """Process a frame of data

        f (string): 'NodeID val1 val2 ...'

        This function splits the string into numbers and check its validity.

        'NodeID val1 val2 ...' is the generic data format. If the source uses
        a different format, override this method.

        Return data as a list: [NodeID, val1, val2]

        """

        # Log data
        self._log.debug(str(cargo.uri) + " NEW FRAME : " + str(cargo.rawdata))

        rxc = cargo
        decoded = []
        node = str(rxc.nodeid)
        datacode = True

        # Discard if data is non-existent
        if len(rxc.realdata) < 1:
            self._log.warning(str(cargo.uri) + " Discarded RX frame 'string too short' : " + str(rxc.realdata))
            return False

        # Parse the ESP format string
        for item in rxc.realdata.split():
          decoded.append(int(item))

        # check if node is listed and has individual scales for each value
        if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'scales' in ehc.nodelist[node]['rx']:
            scales = ehc.nodelist[node]['rx']['scales']
            # === Removed check for scales length so that failure mode is more gracious ===
            # Discard the frame & return 'False' if it doesn't match the number of scales
            # if len(decoded) != len(scales):
            #     self._log.warning(str(rxc.uri) + " Scales " + str(scales) + " for RX data : " + str(rxc.realdata) + " not suitable " )
            #     return False
            # else:
                  # Determine the expected number of values to be decoded
                  # Set decoder to "Per value" scaling using scale 'False' as flag
            #     scale = False
            if len(scales)>1:
                scale = False
            else:
                scale = "1"
        else:
            # if node is listed, but has only a single default scale for all values
            if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'scale' in ehc.nodelist[node]['rx']:
                scale = ehc.nodelist[node]['rx']['scale']
            else:
            # when node not listed or has no scale(s) use the interfacers default if specified
                scale = self._settings['scale']

        if not scale == "1":
            for i in range(0, len(decoded), 1):
                x = scale
                if not scale:
                    if i<len(scales):
                        x = scales[i]
                    else:
                        x = 1

                if x != "1":
                    val = decoded[i] * float(x)
                    if val % 1 == 0:
                        decoded[i] = int(val)
                    else:
                        decoded[i] = float(val)

        rxc.realdata = decoded

        names = []
        if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'names' in ehc.nodelist[node]['rx']:
            names = ehc.nodelist[node]['rx']['names']
        rxc.names = names

        nodename = False
        if node in ehc.nodelist and 'nodename' in ehc.nodelist[node]:
            nodename = ehc.nodelist[node]['nodename']
        rxc.nodename = nodename

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


