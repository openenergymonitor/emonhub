"""class EmonHubEmoncmsHTTPInterfacer
"""
import time
import json
from emonhub_interfacer import EmonHubInterfacer

class EmonHubEmoncmsHTTPInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        # Initialization
        super(EmonHubEmoncmsHTTPInterfacer, self).__init__(name)
        
        # add or alter any default settings for this reporter
        # defaults previously defined in inherited emonhub_interfacer
        # here we are just changing the batchsize from 1 to 100
        # and the interval from 0 to 30
        self._defaults.update({'batchsize': 100,'interval': 30})
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
        
        if not 'apikey' in self._settings.keys() or str.__len__(str(self._settings['apikey'])) != 32 \
                or str.lower(str(self._settings['apikey'])) == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
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
        post_url = self._settings['url']+'/input/bulk'+'.json?apikey='
        post_body = "data="+data_string+"&sentat="+str(sentat)

        # logged before apikey added for security
        self._log.info("sending: " + post_url + "E-M-O-N-C-M-S-A-P-I-K-E-Y&" + post_body)

        # Add apikey to post_url
        post_url = post_url + self._settings['apikey']

        # The Develop branch of emoncms allows for the sending of the apikey in the post
        # body, this should be moved from the url to the body as soon as this is widely
        # adopted

        reply = self._send_post(post_url, post_body)
        if reply == 'ok':
            self._log.debug("acknowledged receipt with '" + reply + "' from " + self._settings['url'])
            return True
        else:
            self._log.warning("send failure: wanted 'ok' but got '" +reply+ "'")
            return False
            
            
    def sendstatus(self):
        if not 'apikey' in self._settings.keys() or str.__len__(str(self._settings['apikey'])) != 32 \
                or str.lower(str(self._settings['apikey'])) == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
            return
        
        # MYIP url
        post_url = self._settings['url']+'/myip/set.json?apikey='
        # Print info log
        self._log.info("sending: " + post_url + "E-M-O-N-C-M-S-A-P-I-K-E-Y")
        # add apikey
        post_url = post_url + self._settings['apikey']
        # send request
        reply = self._send_post(post_url,None)
            
    def set(self, **kwargs):
        """

        :param kwargs:
        :return:
        """

        super (EmonHubEmoncmsHTTPInterfacer, self).set(**kwargs)

        for key, setting in self._cms_settings.iteritems():
            #valid = False
            if not key in kwargs.keys():
                setting = self._cms_settings[key]
            else:
                setting = kwargs[key]
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
            elif key == 'senddata':
                self._log.info("Setting " + self.name + " senddata: " + setting)
                self._settings[key] = setting
                continue
            elif key == 'sendstatus':
                self._log.info("Setting " + self.name + " sendstatus: " + setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (setting, self.name, key))
