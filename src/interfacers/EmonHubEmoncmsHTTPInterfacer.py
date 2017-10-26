"""class EmonHubEmoncmsHTTPInterfacer
"""
import time
import json
import urllib2
import httplib
from emonhub_interfacer import EmonHubInterfacer

class EmonHubEmoncmsHTTPInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        # Initialization
        super(EmonHubEmoncmsHTTPInterfacer, self).__init__(name)
        
        self._name = name
        
        self._settings = {
            'subchannels':['ch1'],
            'pubchannels':['ch2'],
            
            'apikey': "",
            'url': "http://emoncms.org",
            'senddata': 1,
            'sendstatus': 0,
            'sendinterval': 30
        }
        
        # Initialize message queue
        self._pub_channels = {}
        self._sub_channels = {}
        
        self.lastsent = time.time()
        self.lastsentstatus = time.time()
        
    def action(self):
    
        now = time.time()
        
        if (now-self.lastsent) > (int(self._settings['sendinterval'])):
            self.lastsent = now
            
            # It might be better here to combine the output from all sub channels 
            # into a single bulk post, most of the time there is only one sub channel
            for channel in self._settings["subchannels"]:
                if channel in self._sub_channels:

                    # only try to prepare and send data if there is any
                    if len(self._sub_channels[channel])>0:

                        bulkdata = []

                        for cargo in self._sub_channels[channel]:
                            # Create a frame of data in "emonCMS format"
                            f = []
                            try:
                                f.append(float(cargo.timestamp))
                                f.append(cargo.nodeid)
                                for i in cargo.realdata:
                                    f.append(i)
                                if cargo.rssi:
                                    f.append(cargo.rssi)
                                #self._log.debug(str(cargo.uri) + " adding frame to buffer => "+ str(f))
                            except:
                                self._log.warning("Failed to create emonCMS frame " + str(f))

                            bulkdata.append(f)

                        # Get the length of the data to be sent
                        bulkdata_length = len(bulkdata)

                        if int(self._settings['senddata']):
                            self._log.debug("Sending bulkdata, length: "+str(bulkdata_length))
                            # Attempt to send the data
                            success = self.bulkpost(bulkdata)
                            self._log.debug("Sending bulkdata, success: "+str(success))
                        else:
                            success = True


                        # if bulk post is successful delete the range posted
                        if success:
                            for i in range(0,bulkdata_length):
                                self._sub_channels[channel].pop(0)
                            #self._log.debug("Deleted sent data from queue")
                            
                        
                        if int(self._settings['senddata']):
                            self._log.debug("Current queue length: "+str(len(self._sub_channels[channel])))

            
        if (now-self.lastsentstatus)> (int(self._settings['sendinterval'])):
            self.lastsentstatus = now
            if int(self._settings['sendstatus']):
                self.sendstatus()
            
    def bulkpost(self,databuffer):
    
        if not 'apikey' in self._settings.keys() or str.__len__(str(self._settings['apikey'])) != 32 \
                or str.lower(str(self._settings['apikey'])) == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
            return False
            
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
            return reply
            
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
        for key,setting in self._settings.iteritems():
            if key in kwargs.keys():
                # replace default
                self._settings[key] = kwargs[key]
