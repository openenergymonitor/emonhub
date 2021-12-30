"""class EmonHubEmoncmsHTTPInterfacer
"""
import time
import json
import requests
import zlib
from binascii import hexlify
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
            'sendstatus': 0,
            'sendnames': 0,
            'compress': 0
        }

        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250

        # maximum buffer size
        self.buffer._maximumEntriesInBuffer = 100000

    def add(self, cargo):
        """Append data to buffer.

        """
        
        f = []
        try:
            f.append(int(cargo.timestamp))
            
            if cargo.nodename and self._settings['sendnames']:
                f.append(cargo.nodename)
            else:
                f.append(cargo.nodeid)
            
            if len(cargo.names) == len(cargo.realdata) and self._settings['sendnames']:
                keyvalues = {}
                for name, value in zip(cargo.names, cargo.realdata):
                    keyvalues[name] = value
                if cargo.rssi:
                    keyvalues['rssi'] = cargo.rssi
                f.append(keyvalues)
            else:
                for i in cargo.realdata:
                    f.append(i)
                if cargo.rssi:
                    f.append(cargo.rssi)
                # Note if number of names and values do not match
                if len(cargo.names) > 0 and self._settings['sendnames']:
                    self._log.warning("cargo.names and cargo.realdata have different lengths - " + str(len(cargo.names)) + " vs " + str(len(cargo.realdata)))
        except:
            self._log.warning("Failed to create emonCMS frame %s", f)

        self.buffer.storeItem(f)

    def _process_post(self, databuffer):
        """Send data to server."""

        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 250 ...]]

        if 'apikey' not in self._settings or len(str(self._settings['apikey'])) != 32 \
                or str(self._settings['apikey']).lower() == 'x' * 32:
            # Return true to clear buffer if the apikey is not set
            return True

        if self._settings['senddata']:
            number_of_frames = len(databuffer)
            data_string = json.dumps(databuffer, separators=(',', ':'))
            
            # Prepare URL string of the form
            # http://domain.tld/emoncms/input/bulk.json?apikey=12345
            # &data=[[0,10,82,23],[5,10,82,23],[10,10,82,23]]
            # &sentat=15' (requires emoncms >= 8.0)

            # time that the request was sent at
            sentat = int(time.time())
            
            # Construct post_url (without apikey)
            post_url = self._settings['url'] + '/input/bulk.json?sentat='+str(sentat)
            
            # If sendnames enabled then always compress:
            if self._settings['sendnames']:
                self._settings['compress'] = True
            
            # Compress if enabled
            if self._settings['compress']:
                json_str_size = len(data_string)
                # Compress data and encode as hex string.
                compressed = zlib.compress(data_string.encode())
                compression_ratio = len(compressed) / json_str_size
                # Only use compression if it makes sense!
                if compression_ratio<1.0:
                    post_body = compressed
                    # Set compression flag (cb = compression binary).
                    post_url = post_url + "&cb=1"
                    self._log.info("sending: %s (%d bytes of data, %d frames, compressed)", post_url, len(post_body),number_of_frames)
                    self._log.info("compression ratio: %d%%",compression_ratio*100)
                else: 
                    post_body = {'data': data_string}
                    self._log.info("sending: %s (%d bytes of data, %d frames, uncompressed)", post_url, len(data_string),number_of_frames)
                    self._log.info("compression ratio: %d%%, sent original",compression_ratio*100)
            else: 
                post_body = {'data': data_string}
                self._log.info("sending: %s (%d bytes of data, %d frames, uncompressed)", post_url, len(data_string),number_of_frames)
            
            result = False
            try:
                reply = requests.post(post_url, post_body, timeout=60, headers={'Authorization': 'Bearer '+self._settings['apikey']})
                reply.raise_for_status()  # Raise an exception if status code isn't 200
                result = reply.text
            except requests.exceptions.RequestException as ex:
                self._log.warning("%s couldn't send to server: %s", self.name, ex)
                return False

            if result == 'ok':
                self._log.debug("acknowledged receipt with '%s' from %s", result, self._settings['url'])
                return True
            else:
                self._log.warning("send failure: wanted 'ok' but got '%s'", result)
                return False
        
        # Sends status to myip module if enabled
        if self._settings['sendstatus']:
            post_url = self._settings['url'] + '/myip/set.json?apikey='
            self._log.info("sending: " + post_url + "E-M-O-N-C-M-S-A-P-I-K-E-Y")
            post_url = post_url + self._settings['apikey']
            try:
                reply = requests.get(post_url, timeout=60)
                reply.raise_for_status()
                # self._log.debug(reply.text)
            except requests.exceptions.RequestException as ex:
                self._log.warning("%s couldn't send myip status update to server: %s", self.name, ex)

        return True

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
                self._settings[key] = int(setting)
                continue
            elif key == 'sendstatus':
                self._log.info("Setting %s sendstatus: %s", self.name, setting)
                self._settings[key] = int(setting)
                continue
            elif key == 'sendnames':
                self._log.info("Setting " + self.name + " sendnames: " + str(setting))
                self._settings[key] = bool(int(setting))
                continue
            elif key == 'compress':
                self._log.info("Setting " + self.name + " compress: " + str(setting))
                self._settings[key] = bool(int(setting))
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
