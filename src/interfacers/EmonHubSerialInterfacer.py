import serial
from emonhub_interfacer import EmonHubInterfacer

import Cargo

"""class EmonhubSerialInterfacer

Monitors the serial port for data

"""

class EmonHubSerialInterfacer(EmonHubInterfacer):

    def __init__(self, name, com_port='', com_baud=9600):
        """Initialize interfacer

        com_port (string): path to COM port

        """

        # Initialization
        super().__init__(name)

        self._connect_failure_count = 0

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
        #    self._log.debug("Invalid 'com_baud': %d | Default of 9600 used", com_baud)
        #    com_baud = 9600
        try:
            s = serial.Serial(com_port, com_baud, timeout=0)
            self._log.debug("Opening serial port: %s @ %s bits/s", com_port, com_baud)
            self._connect_failure_count = 0
        except serial.SerialException as e:
            self._connect_failure_count += 1
            if self._connect_failure_count==1:
                self._log.error("Could not open serial port: %s @ %s bits/s (retry every 10s)", com_port, com_baud)
                
            s = False
            # raise EmonHubInterfacerInitError('Could not open COM port %s' % com_port)
        return s

    def read(self):
        """Read data from serial port and process if complete line received.

        Return data as a list: [NodeID, val1, val2]

        """

        if not self._ser:
            return False

        # Read serial RX
        self._rx_buf = self._rx_buf + self._ser.readline().decode()

        # If line incomplete, exit
        if '\r\n' not in self._rx_buf:
            return

        # Remove CR,LF
        f = self._rx_buf[:-2]

        # Reset buffer
        self._rx_buf = ''

        # Create a Payload object
        c = Cargo.new_cargo(rawdata=f)

        f = f.split()

        if int(self._settings['nodeoffset']):
            c.nodeid = int(self._settings['nodeoffset'])
            c.realdata = f
        else:
            c.nodeid = int(f[0])
            c.realdata = f[1:]

        return c
