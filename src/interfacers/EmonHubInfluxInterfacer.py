"""class EmonHubInfluxInterfacer
"""
import time
import requests
from emonhub_interfacer import EmonHubInterfacer

class EmonHubInfluxInterfacer(EmonHubInterfacer):

    def __init__(self, name, influx_host='localhost', influx_interval=30, influx_port=8086, influx_user='emoncms', influx_passwd='emoncmspw', influx_db='emoncms'):
        # Initialization
        super().__init__(name)

        self._defaults.update({'batchsize': 100, 'interval': influx_interval })
        self._settings.update(self._defaults)

        # interfacer specific settings
        self._influx_settings = {
            'prefix': 'prefix'
        }
        self._settings.update(self._influx_settings)

        self.init_settings.update({
            'influx_host': influx_host,
            'influx_port': influx_port,
            'influx_user': influx_user,
            'influx_passwd': influx_passwd,
            'influx_db': influx_db
        })

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
        timestamp = int(time.time_ns())

        metrics = []
        for frame in databuffer:
            nodename = frame['node']

            for inputname, value in frame['data'].items():
                # path
                path = inputname + ',prefix=' + self._settings['prefix'] + ',node=' + nodename
                # payload
                payload = str(value)
                # timestamp
                #timestamp = frame['timestamp']

                metrics.append(path + " value=" + payload + " " + str(timestamp))

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

        host = self.init_settings['influx_host'].strip("[']")
        port = int(self.init_settings['influx_port'].strip("[']"))
        url = "http://" + host + ":" + str(port) + "/write"
        self._log.debug("Influx target: %s", url)
        message = '\n'.join(metrics) + '\n'
        self._log.debug("Influx data: %s", message )
        params = {'db': self.init_settings['influx_db'], 'u': self.init_settings['influx_user'], 'p': self.init_settings['influx_passwd']}

        try:
            requests.post(url, params=params, data=message)
        except requests.exceptions.RequestException as e:
            self._log.error(e)
            return False

        return True

    def set(self, **kwargs):
        super().set(**kwargs)
        for key, setting in self._influx_settings.items():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._influx_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

    """
    def set(self, **kwargs):
        super ().set(**kwargs)
        for key, setting in self._influx_settings.items():
            #valid = False
            if key not in kwargs:
                setting = self._influx_settings[key]
            else:
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'influx_host':
                self._log.info("Setting %s influx_host: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'influx_port':
                self._log.info("Setting %s influx_port: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'prefix':
                self._log.info("Setting %s prefix: %s", self.name, setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
    """
