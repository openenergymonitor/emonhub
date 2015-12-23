import socket
import select
import Cargo

from pydispatch import dispatcher
from emonhub_interfacer import EmonHubInterfacer

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
        c = Cargo.new_cargo(rawdata=f)

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

