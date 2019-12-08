"""class EmonHubGraphiteInterfacer
"""
import time
import socket
from emonhub_interfacer import EmonHubInterfacer

class EmonHubGraphiteInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        # Initialization
        super().__init__(name)

        self._defaults.update({'batchsize': 100, 'interval': 30})
        self._settings.update(self._defaults)

        # interfacer specific settings
        self._graphite_settings = {
            'graphite_host': 'localhost',
            'graphite_port': '2003',
            'prefix': 'emonpi'
        }

        self.lastsent = time.time()
        self.lastsentstatus = time.time()

        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250

    def add(self, cargo):
        """Append data to buffer.

          format: {"emontx":{"power1":100,"power2":200,"power3":300}}

        """

        nodename = str(cargo.nodeid)
        if cargo.nodename:
            nodename = cargo.nodename

        f = {}
        f['node'] = nodename
        f['data'] = {}

        # FIXME replace with zip
        for i in range(len(cargo.realdata)):
            name = str(i + 1)
            if i < len(cargo.names):
                name = cargo.names[i]
            value = cargo.realdata[i]
            f['data'][name] = value

        if cargo.rssi:
            f['data']['rssi'] = cargo.rssi

        self.buffer.storeItem(f)


    def _process_post(self, databuffer):
        timestamp = int(time.time())

        metrics = []
        for frame in databuffer:
            nodename = frame['node']

            for inputname, value in frame['data'].items():
                # path
                path = self._settings['prefix'] + '.' + nodename + "." + inputname
                # payload
                payload = str(value)
                # timestamp
                #timestamp = frame['timestamp']

                metrics.append(path + " " + payload + " " + str(timestamp))

        return self._send_metrics(metrics)

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

        host = str(self._settings['graphite_host']).strip('[\'\']')
        port = int(str(self._settings['graphite_port']).strip('[\'\']'))
        self._log.debug("Graphite target: {}:{}".format(host, port))
        message = '\n'.join(metrics) + '\n'
        self._log.debug("Sending metrics:\n" + message)

        try:
            sock = socket.socket()
            sock.connect((host, port))
            sock.sendall(message)
            sock.close()
        except socket.error as e:
            self._log.error(e)
            return False

        return True

    def set(self, **kwargs):
        super().set(**kwargs)
        for key, setting in self._graphite_settings.items():
            if key in kwargs:
                # replace default
                self._settings[key] = kwargs[key]

    """
    def set(self, **kwargs):
        super ().set(**kwargs)
        for key, setting in self._graphite_settings.items():
            #valid = False
            if key not in kwargs:
                setting = self._graphite_settings[key]
            else:
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'graphite_host':
                self._log.info("Setting " + self.name + " graphite_host: " + setting)
                self._settings[key] = setting
                continue
            elif key == 'graphite_port':
                self._log.info("Setting " + self.name + " graphite_port: " + setting)
                self._settings[key] = setting
                continue
            elif key == 'prefix':
                self._log.info("Setting " + self.name + " prefix: " + setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (setting, self.name, key))
    """
