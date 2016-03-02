import time
import serial
import Cargo
from pydispatch import dispatcher
import emonhub_interfacer as ehi

"""class EmonhubSerialInterfacer

Monitors the serial port for data

"""


class EmonHubVEDirectInterfacer(ehi.EmonHubInterfacer):

    (WAIT_HEADER, IN_KEY, IN_VALUE, IN_CHECKSUM) = range(4)

    def __init__(self, name, com_port='', com_baud=9600, toextract='' , poll_interval=30):
        """Initialize interfacer

        com_port (string): path to COM port

        """

        # Initialization
        super(EmonHubVEDirectInterfacer, self).__init__(name)

        # Open serial port
        self._ser = self._open_serial_port(com_port, com_baud)

        # Initialize RX buffer
        self._rx_buf = ''

	#VE Direct requirements
        self.header1 = '\r'
        self.header2 = '\n'
        self.delimiter = '\t'
        self.key = ''
        self.value = ''
        self.bytes_sum = 0;
        self.state = self.WAIT_HEADER
        self.dict = {}
	self.poll_interval = int(poll_interval)
	self.last_read = time.time()

        #Parser requirments
        self._extract = toextract
        #print "init system with to extract %s"%self._extract


    def input(self, byte):
        """
	Parse serial byte code from VE.Direct
	"""
        if self.state == self.WAIT_HEADER:
            self.bytes_sum += ord(byte)
            if byte == self.header1:
                self.state = self.WAIT_HEADER
            elif byte == self.header2:
                self.state = self.IN_KEY

            return None
        elif self.state == self.IN_KEY:
            self.bytes_sum += ord(byte)
            if byte == self.delimiter:
                if (self.key == 'Checksum'):
                    self.state = self.IN_CHECKSUM
                else:
                    self.state = self.IN_VALUE
            else:
                self.key += byte
            return None
        elif self.state == self.IN_VALUE:
            self.bytes_sum += ord(byte)
            if byte == self.header1:
                self.state = self.WAIT_HEADER
                self.dict[self.key] = self.value;
                self.key = '';
                self.value = '';
            else:
                self.value += byte
            return None
        elif self.state == self.IN_CHECKSUM:
            self.bytes_sum += ord(byte)
            self.key = ''
            self.value = ''
            self.state = self.WAIT_HEADER
            if (self.bytes_sum % 256 == 0):
                self.bytes_sum = 0
                return self.dict
            else:
                self.bytes_sum = 0

        else:
            raise AssertionError()

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

    def parse_package(self,data):
        """
        Convert package from vedirect dictionary format to emonhub expected format

        """
        clean_data = "%s"%self._settings['nodeoffset']
        for key in self._extract:
            if data.has_key(key):
                    #Emonhub doesn't like strings so we convert them to ints
                    tempval = 0
                    try:
                        tempval = float(data[key])
                    except Exception,e:
			tempval = data[key]
                    if not isinstance(tempval,float):
                       if data[key] == "OFF":
                          data[key] = 0
                       else:
                          data[key] = 1

		    clean_data = clean_data + " " + str(data[key])
	return clean_data


    def _read_serial(self):
        self._log.debug(" Starting Serial read")
        try:
            while self._rx_buf == '':
		    byte = self._ser.read(1)
		    packet = self.input(byte)
		    if packet != None:
			self._rx_buf = packet

        except Exception,e:
            self._log.error(e)
            self._rx_buf = ""


    def read(self):
        """Read data from serial port and process if complete line received.

        Return data as a list: [NodeID, val1, val2]

        """

        # Read serial RX
        now = time.time()
        if not (now - self.last_read) > self.poll_interval:
            #self._log.debug(" Waiting for %s seconds "%(str(now - self.last_read)))
            # Wait to read based on poll_interval
	        return

        # Read from serial
        self._read_serial()
        # Update last read time
        self.last_read = now
        # If line incomplete, exit
        if self._rx_buf == None:
            return

        #Sample data looks like {'FW': '0307', 'SOC': '1000', 'Relay': 'OFF', 'PID': '0x203', 'H10': '6', 'BMV': '700', 'TTG': '-1', 'H12': '0', 'H18': '0', 'I': '0', 'H11': '0', 'Alarm': 'OFF', 'CE': '0', 'H17': '9', 'P': '0', 'AR': '0', 'V': '26719', 'H8': '29011', 'H9': '0', 'H2': '0', 'H3': '0', 'H1': '-1633', 'H6': '-5775', 'H7': '17453', 'H4': '0', 'H5': '0'}

        # Create a Payload object
        c = Cargo.new_cargo(rawdata = self._rx_buf)
        f = self.parse_package(self._rx_buf)
        f = f.split()

        # Reset buffer
        self._rx_buf = ''

        if f:
	        if int(self._settings['nodeoffset']):
                    c.nodeid = int(self._settings['nodeoffset'])
                    c.realdata = f[1:]
                else:
                    self._log.error("nodeoffset needed in emonhub configuratio, make sure it exits ans is integer ")
                    pass

        return c

