import re
import Cargo
from . import EmonHubSerialInterfacer as ehi

"""class EmonHubTx3eInterfacer

EmonHub Serial Interfacer key:value pair format
e.g: ct1:0,ct2:0,ct3:0,ct4:0,vrms:524,pulse:0
for csv format use the EmonHubSerialInterfacer

"""


class EmonHubTx3eInterfacer(ehi.EmonHubSerialInterfacer):

    def __init__(self, name, com_port='', com_baud=9600):
        """Initialize interfacer

        com_port (string): path to COM port e.g /dev/ttyUSB0
        com_baud (numeric): typically 115200 now for emontx etc

        """

        # Initialization
        super().__init__(name, com_port, com_baud)

        self._settings.update({
            'nodename': ""
        })

        # Initialize RX buffer
        self._rx_buf = ''

    def read(self):
        """Read data from serial port and process if complete line received.

        Read data format is key:value pairs e.g:
        ct1:0,ct2:0,ct3:0,ct4:0,vrms:524,pulse:0

        """

        if not self._ser:
            return False

        # Read serial RX
        self._rx_buf = self._rx_buf + self._ser.readline().decode()

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
        values = []
        names = []

        for item in f.split(','):
            parts = item.split(':')
            if len(parts) == 2:
                # check for alphanumeric input name
                if re.match(r'^[\w-]+$', parts[0]):
                    # check for numeric value
                    value = 0
                    try:
                        value = float(parts[1])
                    except Exception:
                        self._log.debug("input value is not numeric: " + parts[1])

                    names.append(parts[0])
                    values.append(value)
                else:
                    self._log.debug("invalid input name: " + parts[0])

        if self._settings["nodename"] != "":
            c.nodename = self._settings["nodename"]
            c.nodeid = self._settings["nodename"]
        else:
            c.nodeid = int(self._settings['nodeoffset'])

        c.realdata = values
        c.names = names

        if len(values) == 0:
            return False

        return c

    def set(self, **kwargs):
        for key, setting in self._settings.items():
            if key in kwargs:
                # replace default
                # self._log.debug(kwargs[key])
                self._settings[key] = kwargs[key]
