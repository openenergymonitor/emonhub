"""class EmonHubEmoncmsHTTPInterfacer
"""
import time
import json
import requests
from emonhub_interfacer import EmonHubInterfacer

class EmonHubEmoncmsHTTPInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        # Initialization
        super().__init__(name)

        # add or alter any default settings for this reporter
        # defaults previously defined in inherited emonhub_interfacer
        # here we are just changing the batchsize from 1 to 100
        # and the interval from 0 to 30
        self._defaults.update({'batchsize': 100, 'interval': 30})
        # This line will stop the default values printing to logfile at start-up
        self._settings.update(self._defaults)

        # interfacer specific settings
        self._cms_settings = {
            'apikey': "",
            'url': "http://emoncms.org",
            'senddata': 1,
            'sendstatus': 0
        }

        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250

        # maximum buffer size
        self.buffer._maximumEntriesInBuffer = 100000

    def _process_post(self, databuffer):
        """Send data to server."""

        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 250 ...]]

        if 'apikey' not in self._settings or len(str(self._settings['apikey'])) != 32 \
                or str(self._settings['apikey']).lower() == 'x' * 32:
            # Return true to clear buffer if the apikey is not set
            return True

        data_string = json.dumps(databuffer, separators=(',', ':'))

        # Prepare URL string of the form
        # http://domain.tld/emoncms/input/bulk.json?apikey=12345
        # &data=[[0,10,82,23],[5,10,82,23],[10,10,82,23]]
        # &sentat=15' (requires emoncms >= 8.0)

        # time that the request was sent at
        sentat = int(time.time())

        # Construct post_url (without apikey)
        post_url = self._settings['url'] + '/input/bulk.json?'
        
        self._log.info("sending: %s data=%s&sentat=%s&apikey=E-M-O-N-C-M-S-A-P-I-K-E-Y", post_url, data_string, sentat)
        
        result = False
        try:
            reply = requests.post(post_url, {'apikey': self._settings['apikey'], 'data': data_string, 'sentat': str(sentat)}, timeout=60)
            reply.raise_for_status()  # Raise an exception if status code isn't 200
            result = reply.text
        except requests.exceptions.RequestException as ex:
            self._log.warning("%s couldn't send to server: %s", self.name, ex)

        if result == 'ok':
            self._log.debug("acknowledged receipt with '%s' from %s", result, self._settings['url'])
            return True
        else:
            self._log.warning("send failure: wanted 'ok' but got '%s'", result)
            return False

    def sendstatus(self):
        if 'apikey' not in self._settings or len(str(self._settings['apikey'])) != 32 \
                or str(self._settings['apikey']).lower() == 'x' * 32:
            return

        # MYIP url
        post_url = self._settings['url'] + '/myip/set.json?apikey='
        # Print info log
        self._log.info("sending: " + post_url + "E-M-O-N-C-M-S-A-P-I-K-E-Y")
        # add apikey
        post_url = post_url + self._settings['apikey']
        
        try:
            reply = requests.get(post_url, timeout=60)
            reply.raise_for_status()
            result = reply.text
        except requests.exceptions.RequestException as ex:
            self._log.warning("%s couldn't send myip status update to server: %s", self.name, ex)

    def set(self, **kwargs):
        """

        :param kwargs:
        :return:
        """

        super().set(**kwargs)

        for key, setting in self._cms_settings.items():
            #valid = False
            if key not in kwargs:
                setting = self._cms_settings[key]
            else:
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'apikey':
                if setting.lower().startswith('xxxx'):  # FIXME compare whole string to 'x'*32?
                    self._log.warning("Setting %s apikey: obscured", self.name)
                elif len(setting) == 32:
                    self._log.info("Setting %s apikey: set", self.name)
                elif setting == "":
                    self._log.info("Setting %s apikey: null", self.name)
                else:
                    self._log.warning("Setting %s apikey: invalid format", self.name)
                    continue
                self._settings[key] = setting
                # Next line will log apikey if uncommented (privacy ?)
                #self._log.debug("%s apikey: %s", self.name, setting)
                continue
            elif key == 'url' and setting.startswith("http"):
                self._log.info("Setting %s url: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'senddata':
                self._log.info("Setting %s senddata: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'sendstatus':
                self._log.info("Setting %s sendstatus: %s", self.name, setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
