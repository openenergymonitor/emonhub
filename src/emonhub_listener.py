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

import emonhub_coder as ehc

"""class EmonHubListener

Monitors a data source. 

This almost empty class is meant to be inherited by subclasses specific to
their data source.

"""


class EmonHubListener(object):

    def __init__(self):
        
        # Initialize logger
        self._log = logging.getLogger("EmonHub")

        # Initialise settings
        self.name = ''
        self._settings = {'defaultdatacode': ''}
        
    def close(self):
        """Close socket."""
        pass

    def read(self):
        """Read data from socket and process if complete line received.

        Return data as a list: [NodeID, val1, val2]
        
        """
        pass

    def _process_frame(self, f):
        """Process a frame of data

        f (string): 'NodeID val1 val2 ...'

        This function splits the string into numbers and check its validity.

        'NodeID val1 val2 ...' is the generic data format. If the source uses 
        a different format, override this method.
        
        Return data as a list: [NodeID, val1, val2]

        """

        # Log data
        self._log.info(" NEW FRAME : " + f)
        
        # Get an array out of the space separated string
        received = f.strip().split(' ')

        # Validate frame
        if not self._validate_frame(received):
            self._log.debug('Discard RX Frame "Failed validation"')
            return

        received = self._decode_frame(received)

        if received:
            self._log.debug("   Node : " + str(received[0]))
            self._log.debug(" Values : " + str(received[1:]))
            return received
        else:
            return

    def _validate_frame(self, received):
        """Validate a frame of data

        This function performs logical tests to filter unsuitable data.
        Each test discards frame with a log entry if False

        Returns True if data frame passes tests.

        """
        
        # Discard if frame not of the form [node, val1, ...]
        # with number of elements at least 2
        if len(received) < 2:
            self._log.warning("Discarded RX frame 'string too short' : " + str(received))
            return False

        # Discard if anything non-numerical found
        try:
            [float(val) for val in received]
        except Exception:
            self._log.warning("Discarded RX frame 'non-numerical content' : " + str(received))
            return False

        # If it passes all the checks return True
        return True

    def _decode_frame(self, received):
        """Decodes a frame of data

        Performs decoding of data types

        Returns decoded string of data.

        """

        node = received[0]
        data = received[1:]

        datacode = self._settings['defaultdatacode']

        if not datacode:
                  return received

        if len(data) % ehc.check_datacode(datacode) != 0:
            self._log.warning("RX data length: " + str(len(data)) +
                              " is not valid for data code " + str(datacode))
            return False
        else:
            count = len(data) / ehc.check_datacode(datacode)

        # Decode the string of data one value at a time into "decoded"
        decoded = []
        bytepos = int(0)
        #v = 0
        for i in range(0, count, 1):
            dc = datacode
            size = int(ehc.check_datacode(dc))
            value = ehc.decode(dc, [int(v) for v in data[bytepos:bytepos+size]])
            bytepos += size
            decoded.append(value)

        # Insert node ID before data
        decoded.insert(0, node)
        return decoded
    
    def set(self, **kwargs):
        """Set configuration parameters.

        **kwargs (dict): settings to be sent. Example:
        {'setting_1': 'value_1', 'setting_2': 'value_2'}
        
        """
        key = 'defaultdatacode'
        value = ''
        try:
            kwargs[key]
        except:
            value = False
        else:
            value = kwargs[key]
            if not ehc.check_datacode(value):
                value = False
        finally:
            if value != self._settings[key]:
                self._settings[key] = value
                self._log.debug("Setting " + self.name + " default datacode : %s", self._settings[key])

    def run(self):
        """Placeholder for background tasks. 
        
        Allows subclasses to specify actions that need to be done on a 
        regular basis. This should be called in main loop by instantiater.
        
        """
        pass

    def _open_serial_port(self, com_port):
        """Open serial port

        com_port (string): path to COM port

        """
        
        self._log.debug('Opening serial port: %s', com_port)
        
        try:
            s = serial.Serial(com_port, 9600, timeout=0)
        except serial.SerialException as e:
            self._log.error(e)
            raise EmonHubListenerInitError('Could not open COM port %s' %
                                           com_port)
        else:
            return s
    
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
            raise EmonHubListenerInitError('Could not open port %s' %
                                           port_nb)
        else:
            return s

"""class EmonhubSerialListener

Monitors the serial port for data

"""


class EmonHubSerialListener(EmonHubListener):

    def __init__(self, com_port):
        """Initialize listener

        com_port (string): path to COM port

        """
        
        # Initialization
        super(EmonHubSerialListener, self).__init__()

        # Open serial port
        self._ser = self._open_serial_port(com_port)
        
        # Initialize RX buffer
        self._rx_buf = ''

    def close(self):
        """Close serial port"""
        
        # Close serial port
        if self._ser is not None:
            self._log.debug("Closing serial port")
            self._ser.close()

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

        # Process data frame
        return self._process_frame(f)

"""class EmonHubJeeListener

Monitors the serial port for data from "Jee" type device

"""


class EmonHubJeeListener(EmonHubSerialListener):

    def __init__(self, com_port):
        """Initialize listener

        com_port (string): path to COM port

        """
        
        # Initialization
        super(EmonHubJeeListener, self).__init__(com_port)

        # Initialize settings
        self._settings = {'baseid': '', 'frequency': '', 'sgroup': '',
                          'sendtimeinterval': '', 'defaultdatacode': ''}
        
        # Initialize time update timestamp
        self._time_update_timestamp = 0

    def _validate_frame(self, received):
        """Validate a frame of data

        This function performs logical tests to filter unsuitable data.
        Each test discards frame with a log entry if False

        Returns True if data frame passes tests.

        """

        # include checks from parent
        super(EmonHubJeeListener, self)._validate_frame(received)

        # Discard information messages
        if (received[0] == '>') or (received[0] == '->'):
            self._log.warning("Discard RX frame 'information' : " + str(received))
            return False
            
        if received[0] == '\x01':
            self._log.info("Ignoring frame consisting of SOH character")
            return False

        # Discard if frame not at least 3 elements
        if len(received) < 3:
            self._log.warning("Discard RX frame 'too short' : " + str(received))
            return False

        # Discard frame if number of elements not odd
        # [node val1_lsb val1_msb val2_lsb val2_msb ...]
        if not (len(received) & 1):
            self._log.warning("Discard RX frame 'element count incorrect': " + str(received))
            return False

        return True

    def set(self, **kwargs):
        """Send configuration parameters to the "Jee" type device through COM port

        **kwargs (dict): settings to be modified. Available settings are
        'baseid', 'frequency', 'sgroup'. Example: 
        {'baseid': '15', 'frequency': '4', 'sgroup': '210'}
        
        """

        # include kwargs from parent
        super(EmonHubJeeListener, self).set(**kwargs)
        
        for key, value in kwargs.iteritems():
            # If radio setting modified, transmit on serial link
            if key in ['baseid', 'frequency', 'sgroup']:
                if value != self._settings[key]:
                    self._settings[key] = value
                    self._log.info("Setting " + self.name + " %s: %s :" % (key, value))
                    string = value
                    if key == 'baseid':
                        string += 'i'
                    elif key == 'frequency':
                        string += 'b'
                    elif key == 'sgroup':
                        string += 'g'
                    self._ser.write(string)
                    # Wait a sec between two settings
                    time.sleep(1)
            elif key == 'sendtimeinterval':
                if value != self._settings[key]:
                    self._log.info("Setting " + self.name + " send time interval : %s", value)
                    self._settings[key] = value

    def run(self):
        """Actions that need to be done on a regular basis. 
        
        This should be called in main loop by instantiater.
        
        """

        now = time.time()

        # Broadcast time to synchronize emonGLCD
        interval = int(self._settings['sendtimeinterval'])
        if interval:  # A value of 0 means don't do anything
            if now - self._time_update_timestamp > interval:
                self._send_time()
                self._time_update_timestamp = now
    
    def _send_time(self):
        """Send time over radio link to synchronize emonGLCD

        The radio module can be used to broadcast time, which is useful
        to synchronize emonGLCD in particular.
        Beware, this is know to garble the serial link on RFM2Piv1
        sendtimeinterval defines the interval in seconds between two time
        broadcasts. 0 means never.

        """

        now = datetime.datetime.now()

        self._log.debug("Broadcasting time: %d:%d" % (now.hour, now.minute))

        self._ser.write("00,%02d,%02d,00,s" % (now.hour, now.minute))

"""class EmonHubSocketListener

Monitors a socket for data, typically from ethernet link

"""


class EmonHubSocketListener(EmonHubListener):

    def __init__(self, port_nb):
        """Initialize listener

        port_nb (string): port number on which to open the socket

        """
 
        # Initialization
        super(EmonHubSocketListener, self).__init__()

        # Open socket
        self._socket = self._open_socket(port_nb)

        # Initialize RX buffer for socket
        self._sock_rx_buf = ''

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
        if '\r\n' in self._sock_rx_buf:
            
            # Process and return first frame in buffer:
            f, self._sock_rx_buf = self._sock_rx_buf.split('\r\n', 1)
            return self._process_frame(f)

"""class EmonHubJeeListenerRepeater

Monitors the serial port for data from "Jee" type device,
and repeats on RF link the frames received through a socket

"""


class EmonHubJeeListenerRepeater(EmonHubJeeListener):

    def __init__(self, com_port, port_nb):
        """Initialize listener

        com_port (string): path to COM port
        port_nb (string): port number on which to open the socket

        """
        
        # Initialization
        super(EmonHubJeeListenerRepeater, self).__init__(com_port)

        # Open socket
        self._socket = self._open_socket(port_nb)
        
        # Initialize RX buffer for socket
        self._sock_rx_buf = ''

    def close(self):
        """Close socket and serial port"""
        
        # Close socket
        if self._socket is not None:
            self._log.debug('Closing socket')
            self._socket.close()

        # Close serial port
        super(EmonHubJeeListenerRepeater, self).close()

    def run(self):
        """Monitor socket and repeat data if complete frame received."""

        # Execute run() method from parent
        super(EmonHubJeeListenerRepeater, self).run()
                        
        # Check if data received on socket
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
        if '\r\n' in self._sock_rx_buf:
            
            # Send first frame in buffer:
            f, self._sock_rx_buf = self._sock_rx_buf.split('\r\n', 1)
            self._log.info("Sending frame: %s", f)
            self._ser.write(f)

"""class EmonHubListenerInitError

Raise this when init fails.

"""


class EmonHubListenerInitError(Exception):
    pass
