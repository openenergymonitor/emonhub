"""class EmonHubEmoncmsHTTPInterfacer
"""
import zlib
import time
import json
import urllib2
import httplib
import redis

from sys import getsizeof as size
from pydispatch import dispatcher
from emonhub_interfacer import EmonHubInterfacer

class EmonHubEmoncmsHTTPInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        # Initialization
        super(EmonHubEmoncmsHTTPInterfacer, self).__init__(name)
        
        self._name = name
        self._data_size = 0
        self._settings = {
            'subchannels':['ch1'],
            'pubchannels':['ch2'],
            'compression':True,   
            'apikey': "",
            'url': "http://emoncms.org",
            'senddata': 1,
            'sendstatus': 0,
            'data_send_interval':30,
            'status_send_interval':60,
            'buffer_size':10,
	    'site_id':5
        }
        
	self._compression_level = 9
        self.buffer = []
        self.lastsent = time.time() 
        self.lastsentstatus = time.time()

    def receiver(self, cargo):
    
        # Create a frame of data in "emonCMS format"
        f = []
        f.append(int(cargo.timestamp))
        f.append(cargo.nodeid)
        for i in cargo.realdata:
            f.append(i)
        if cargo.rssi:
            f.append(cargo.rssi)

        self._log.debug(str(cargo.uri) + " adding frame to buffer => "+ str(f))
	# If buffer is full don't append
        # Append to bulk post buffer
	if len(self.buffer) <= self._settings['buffer_size']:
		self.buffer.append(f)
	else:
		self._log.warning("buffer full no more data points will be added")
        
    def action(self):
    
        now = time.time()
        
        if (now-self.lastsent) > int(self._settings['data_send_interval']):
            self.lastsent = now
            # print json.dumps(self.buffer)
            if int(self._settings['senddata']):
                # Send bulk post 
                if self.bulkpost(self.buffer):
                    # Clear buffer if successfull else keep buffer and try again
		    self.buffer = []
            
        if (now-self.lastsentstatus) > int(self._settings['status_send_interval']):
            self.lastsentstatus = now
            if int(self._settings['sendstatus']):
                self.sendstatus()
            
    def bulkpost(self,databuffer):
        self._log.info("Prepping bulk post: " + str( databuffer ))
    	#Removing length check fo apikey
        if not 'apikey' in self._settings.keys() or str.lower(str(self._settings['apikey'])) == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
            self._log.error("API key not found skipping: " + str( databuffer ))
            return False
        self._log.debug("data string %s "%databuffer)    
        data_string = json.dumps(databuffer, separators=(',', ':'))
        
	
        # Prepare URL string of the form
        # http://domain.tld/emoncms/input/bulk.json?apikey=12345
        # &data=[[0,10,82,23],[5,10,82,23],[10,10,82,23]]
        # &sentat=15' (requires emoncms >= 8.0)

        # time that the request was sent at
        sentat = int(time.time())

        # Construct post_url (without apikey)
        post_url = self._settings['url']+'/input/bulk'+'.json?apikey='
        post_body = data_string

	if self._settings["compression"]:
		post_body = zlib.compress(post_body, self._compression_level)

        # Add apikey to post_url
        post_url = post_url + self._settings['apikey'] + "&" + "site_id=" + self._settings['site_id'] + "&time="+str(sentat)

        # logged before apikey added for security
        self._log.info("sending: " + post_url + " body:" +post_body)

        # The Develop branch of emoncms allows for the sending of the apikey in the post
        # body, this should be moved from the url to the body as soon as this is widely
        # adopted

        reply = self._send_post(post_url, post_body)
        if reply.lower().strip() == 'ok':
            self._log.debug("acknowledged receipt with '" + reply + "' from " + self._settings['url'])
            return True
        else:
            self._log.warning("send failure: wanted 'ok' but got '" +reply+ "'")
            self._log.warning("Keeping buffer till successfull attempt, buffer length: " + str(len(self.buffer)))
            return False
            
    def _send_post(self, post_url, post_body=None):
        """

        :param post_url:
        :param post_body:
        :return: the received reply if request is successful
        """
        """Send data to server.

        data (list): node and values (eg: '[node,val1,val2,...]')
        time (int): timestamp, time when sample was recorded

        return True if data sent correctly

        """

        reply = ""
        request = urllib2.Request(post_url, post_body)
	if self._settings["compression"]:
		#request.add_header('Content-Type','text/plain')
		request.add_header('Content-Encoding','gzip')
	self._data_size = self._data_size + size(post_body)
        try:
            response = urllib2.urlopen(request, timeout=60)
        except urllib2.HTTPError as e:
            self._log.warning(self.name + " couldn't send to server, HTTPError: " +
                              str(e.code))
        except urllib2.URLError as e:
            self._log.warning(self.name + " couldn't send to server, URLError: " +
                              str(e.reason))
        except httplib.HTTPException:
            self._log.warning(self.name + " couldn't send to server, HTTPException")
        except Exception:
            import traceback
            self._log.warning(self.name + " couldn't send to server, Exception: " +
                              traceback.format_exc())
        else:
            reply = response.read()
        finally:
            self._log.debug("amount of data sent is %s"%self._data_size)
            return reply
            
    def sendstatus(self):
        if not 'apikey' in self._settings.keys() or str.lower(str(self._settings['apikey'])) == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
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
        for key,setting in self._settings.iteritems():
            if key in kwargs.keys():
                # replace default
                self._settings[key] = kwargs[key]
        
        # Subscribe to internal channels
        for channel in self._settings["subchannels"]:
            dispatcher.connect(self.receiver, channel)
            self._log.debug(self._name+" Subscribed to channel' : " + str(channel))

