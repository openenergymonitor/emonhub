"""class EmonHubGraphiteInterfacer
"""
import time
import json
import socket
import httplib
from pydispatch import dispatcher
from emonhub_interfacer import EmonHubInterfacer

class EmonHubGraphiteInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        # Initialization
        super(EmonHubGraphiteInterfacer, self).__init__(name)

        self._name = name

        self._settings = {
            'subchannels':['ch1'],
            'pubchannels':['ch2'],
            'graphite_host': 'graphite.example.com',
            'graphite_port': '2003',
            'senddata': 1,
            'sendinterval': 30,
            'prefix': 'emonpi'
        }
        self._log.debug(self._settings)

        self.buffer = []
        self.lastsent = time.time()
        self.lastsentstatus = time.time()

    def receiver(self, cargo):
        self._log.debug('Entering recieve function')
        nodestr = str(cargo.nodeid)
        if cargo.nodename!=False: nodestr = str(cargo.nodename)

        m = []
        # Create a frame of data for graphite
        # path.to.metric <data> <timestamp>
        varid = 1
        for value in cargo.realdata:
            # Variable id or variable name if given
            varstr = str(varid)
            if (varid-1)<len(cargo.names):
                varstr = str(cargo.names[varid-1])
                # Construct path
            path = self._settings['prefix']+'.'+nodestr+"."+varstr
            payload = str(value)

            self._log.debug("Collecting metric: "+path+" "+payload)
            self.buffer.append(path+" "+payload+" "+str(int(cargo.timestamp)))

            varid += 1


    def action(self):

        now = time.time()

        if (now-self.lastsent) > (int(self._settings['sendinterval'])):
            self.lastsent = now
            if int(self._settings['senddata']):
                self._send_metrics(self.buffer)
            self.buffer = []


    def _send_metrics(self, metrics=[]):
        """

        :param post_url:
        :param post_body:
        :return: the received reply if request is successful
        """
        """Send data to server.

        metrics (list): metric path and values (eg: '["path.node1 val1 time","path.node2 val2 time",...]')

        return True if data sent correctly

        """

        host = str(self._settings['graphite_host']).strip('[]')
        port = int(str(self._settings['graphite_port']).strip('[\'\']'))
        self._log.debug("Graphite target: " + host + ":" + port)
        message = '\n'.join(metrics)+'\n'
        self._log.debug("Sending metrics: "+message)

        sock = socket.socket()
        sock.connect((HOST, PORT))
        sock.sendall(message)
        sock.close()

    def set(self, **kwargs):
        for key,setting in self._settings.iteritems():
            if key in kwargs.keys():
                # replace default
                self._settings[key] = kwargs[key]

        # Subscribe to internal channels
        for channel in self._settings["subchannels"]:
            dispatcher.connect(self.receiver, channel)
            self._log.debug(self._name+" Subscribed to channel' : " + str(channel))

