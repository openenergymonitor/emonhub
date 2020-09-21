import threading
import datetime
import time

from BaseHTTPServer import BaseHTTPRequestHandler
from Queue import Queue
from SocketServer import TCPServer, ThreadingMixIn
from urlparse import parse_qs

import Cargo
import emonhub_coder as ehc
from emonhub_interfacer import EmonHubInterfacer

class ThreadedTCPServer(ThreadingMixIn, TCPServer):
    def serve_forever(self, queue):
        self.RequestHandlerClass.queue = queue
        TCPServer.serve_forever(self)

class ServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = parse_qs(self.path[18:])
        self.queue.put(data)


class EmonHubSmilicsInterfacer(EmonHubInterfacer):
    """ Interface for the Smilics Wibee

    Listen for get request on the specified port
    """

    def __init__(self, name, port):
        """
        Args:
            name (str): Configuration name.
            port (int): The port the webserver should listen on.
        """
        super().__init__(name)

        self._settings = {
            'subchannels': ['ch1'],
            'pubchannels': ['ch2'],
        }
        self._queue = Queue()
        self._server = ThreadedTCPServer(("0.0.0.0", int(port)), ServerHandler)

    def close(self):
        """Cleanup when the interface closes"""
        if self._server is not None:
            self._log.debug('Closing server')
            self._server.shutdown()
            self._server.server_close()

    def run(self):
        """Starts the server on a new thread and processes the queue"""
        server_thread = threading.Thread(target=self._server.serve_forever, args=(self._queue,))
        server_thread.daemon = True
        server_thread.start()

        while not self.stop:
            while not self._queue.empty():
                rxc = self._process_rx(self._queue.get(False))
                self._queue.task_done()

                if rxc:
                    rxc = self._process_rx(rxc)
                    if rxc:
                        for channel in self._settings["pubchannels"]:
                            self._log.debug(str(rxc.uri) + " Sent to channel(start)' : " + str(channel))

                            # Initialize channel if needed
                            if channel not in self._pub_channels:
                                self._pub_channels[channel] = []

                            # Add cargo item to channel
                            self._pub_channels[channel].append(rxc)

                            self._log.debug(str(rxc.uri) + " Sent to channel(end)' : " + str(channel))

            # Don't loop too fast
            time.sleep(0.1)

        self.close()

    def _process_rx(self, smilics_dict):
        """ Converts the data received on the webserver to an instance of
        the Cargo class

        Args:
            smilics_dict: Dict with smilics data.

        Returns:
            Cargo if successful, None otherwise.
        """
        try:
            c = Cargo.new_cargo()
            if 'mac' not in smilics_dict.keys():
                return None

            c.nodeid = smilics_dict['mac'][0]
            if c.nodeid not in ehc.nodelist.keys():
                self._log.debug(str(c.nodeid) + " Not in config")
                return None

            node_config = ehc.nodelist[str(c.nodeid)]

            c.names = node_config['rx']['names']
            c.nodename = node_config['nodename']

            c.realdata = [
                smilics_dict['a1'][0],
                smilics_dict['a2'][0],
                smilics_dict['a3'][0],
                smilics_dict['at'][0],
                smilics_dict['e1'][0],
                smilics_dict['e2'][0],
                smilics_dict['e3'][0],
                smilics_dict['et'][0],
            ]

            c.timestamp = time.mktime(datetime.datetime.now().timetuple())

            return c
        except:
            return None

    def set(self, **kwargs):
        """ Override default settings with settings entered in the config file
        """
        for key, setting in self._settings.iteritems():
            if key in kwargs.keys():
                # replace default
                self._settings[key] = kwargs[key]
