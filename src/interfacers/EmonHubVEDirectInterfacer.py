import time
import serial
import Cargo
from emonhub_interfacer import EmonHubInterfacer

class EmonHubVEDirectInterfacer(EmonHubInterfacer):
    """class EmonhubSerialInterfacer

    Monitors the serial port for data

    """


    WAIT_HEADER, IN_KEY, IN_VALUE, IN_CHECKSUM = range(4)

    def __init__(self, name, com_port='', com_baud=9600, toextract='', poll_interval=30):
        """Initialize interfacer

        com_port (string): path to COM port

        """

        # Initialization
        super().__init__(name)

        # Open serial port
        self._ser = self._open_serial_port(com_port, com_baud)

        # VE Direct state machine requirements
        self.header1 = b'\r'
        self.header2 = b'\n'
        self.delimiter = b'\t'
        self.key = bytearray()
        self.value = bytearray()
        self.bytes_sum = 0
        self.state = self.WAIT_HEADER
        self.dict = {}

        # Parser requirements
        self._extract = toextract
        self.poll_interval = float(poll_interval)

        # Polling timer
        self.last_read = 0.0


    def input(self, byte):
        """
        Parse serial byte code from VE.Direct
        """
        self.bytes_sum += ord(byte)
        if self.state == self.WAIT_HEADER:
            if byte == self.header1:
                self.state = self.WAIT_HEADER
            elif byte == self.header2:
                self.state = self.IN_KEY
        elif self.state == self.IN_KEY:
            if byte == self.delimiter:
                if self.key.decode() == 'Checksum':
                    self.state = self.IN_CHECKSUM
                else:
                    self.state = self.IN_VALUE
            else:
                self.key += byte
        elif self.state == self.IN_VALUE:
            if byte == self.header1:
                self.state = self.WAIT_HEADER
                self.dict[self.key.decode()] = self.value.decode()
                self.key = bytearray()
                self.value = bytearray()
            else:
                self.value += byte
        elif self.state == self.IN_CHECKSUM:
            self.state = self.WAIT_HEADER
            self.key = bytearray()
            self.value = bytearray()
            try:
                if self.bytes_sum % 256 == 0:
                    return self.dict
                self._log.error("Invalid checksum, discarding data")
            finally:
                self.dict = {}
                self.bytes_sum = 0
        else:
            raise RuntimeError("Impossible state")

    def close(self):
        """Close serial port"""

        # Close serial port
        if self._ser is not None:
            self._log.debug("Closing serial port")
            self._ser.close()

    def _open_serial_port(self, com_port, com_baud):
        """Open serial port

        com_port (string): path to COM port
        com_baud (int): baud rate

        """

        try:
            self._log.debug("Opening serial port: %s @ %s bits/s", com_port, com_baud)
            return serial.Serial(com_port, com_baud, timeout=10)
        except serial.SerialException:
            self._log.exception("Open error")

    def parse_package(self, data):
        """
        Convert package from vedirect dictionary format to emonhub expected format

        """
        clean_data = []
        for key in self._extract:
            # Emonhub doesn't like strings so we convert them to floats
            try:
                clean_data.append(float(data[key]))
            except KeyError:
                self._log.warning("Requested key %s missing from received data", key)
                continue
            except ValueError:
                # VEDirect values which aren't numerical are either "OFF" or... something else.
                clean_data.append(0.0 if data[key] == 'OFF' else 1.0)
        return clean_data

    def _read_serial(self):
        self._log.debug("Starting Serial read from %s", self._ser)
        try:
            while True:
                # Read one byte at a time from the serial port and pass it into
                # the input FSM until we have a complete packet, then return it
                packet = self.input(self._ser.read())
                if packet is not None:
                    return packet
        except Exception:  # FIXME Too general Exception. Maybe SerialException?
            self._log.exception("Read error")

    def read(self):
        """Read data from serial port and process if complete line received.
        """

        now = time.time()
        if now - self.last_read <= self.poll_interval:
            # Wait to read based on poll_interval
            return

        rx_buf = self._read_serial()
        self.last_read = now
        # If _read_serial raised an exception, exit
        if rx_buf is None:
            return

        #Sample data looks like {'FW': '0307', 'SOC': '1000', 'Relay': 'OFF', 'PID': '0x203', 'H10': '6', 'BMV': '700', 'TTG': '-1', 'H12': '0', 'H18': '0', 'I': '0', 'H11': '0', 'Alarm': 'OFF', 'CE': '0', 'H17': '9', 'P': '0', 'AR': '0', 'V': '26719', 'H8': '29011', 'H9': '0', 'H2': '0', 'H3': '0', 'H1': '-1633', 'H6': '-5775', 'H7': '17453', 'H4': '0', 'H5': '0'}

        if 'nodeoffset' not in self._settings:
            self._log.error("nodeoffset needed in emonhub configuration, make sure it exists and is integer")

        return Cargo.new_cargo(rawdata=rx_buf,
                               realdata=self.parse_package(rx_buf),
                               nodeid=int(self._settings['nodeoffset']))
