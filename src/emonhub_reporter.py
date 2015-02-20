"""

  This code is released under the GNU Affero General Public License.
  
  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import urllib2
import httplib
import time
import logging
import json
import threading

import emonhub_buffer as ehb

from pydispatch import dispatcher
  
"""class EmonHubReporter

Stores server parameters and buffers the data between two HTTP requests

This class is meant to be inherited by subclasses specific to their 
destination server.

"""


class EmonHubReporter(threading.Thread):

    def __init__(self, reporterName, buffer_type="memory", buffer_size=1000, **kwargs):
        """Create a server data buffer initialized with server settings."""

        # Initialize logger
        self._log = logging.getLogger("EmonHub")

        # Initialise thread
        threading.Thread.__init__(self)
        self.setName(reporterName)

        # Initialise settings
        self.name = reporterName
        self.init_settings = {}
        self._defaults = {'pause': 'off', 'interval': '0', 'batchsize': '1','pub_channels':["ch2"],'sub_channels':["ch1"]}
        self._settings = {}

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)

        # Initialize interval timer's "started at" timestamp
        self._interval_timestamp = 0

        # Create underlying buffer implementation
        self.buffer = ehb.getBuffer(buffer_type)(reporterName, buffer_size, **kwargs)

        # set an absolute upper limit for number of items to process per post
        # number of items posted is the lower of this item limit, buffer_size, or the
        # batchsize, as set in reporter settings or by the default value.
        self._item_limit = buffer_size
        
        self._log.info("Set up reporter '%s' (buffer: %s | size: %s)"
                       % (reporterName, buffer_type, buffer_size))
                
        # Initialise a thread and start the reporter
        self.stop = False
        self.start()
        
        
        
    def set(self, **kwargs):
        """Update settings.
        
        **kwargs (dict): runtime settings to be modified.
        
        url (string): eg: 'http://localhost/emoncms' or 'http://emoncms.org' (trailing slash optional)
        apikey (string): API key with write access
        pause (string): pause status
            'pause' = all  pause fully, nothing posted to buffer or sent (buffer retained)
            'pause' = in   pauses the input only, no add to buffer but flush still functional
            'pause' = out  pauses output only, no flush but data can accumulate in buffer
            'pause' = off  pause is off and reporter is fully operational
        
        """

        for key, setting in self._defaults.iteritems():
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._defaults[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'pause' and str(setting).lower() in ['all', 'in', 'out', 'off']:
                pass
            elif key in ['interval', 'batchsize'] and setting.isdigit():
                pass
            elif key == 'sub_channels' or 'pub_channels':
                pass
            else:
                self._log.warning("In reporter:set '%s' is not a valid setting for %s: %s" % (setting, self.name, key))
            self._settings[key] = setting
            self._log.debug("Setting " + self.name + " " + key + ": " + str(setting))
        
        # Is there a better place to put this?    
        for channel in self._settings["sub_channels"]:
            dispatcher.connect(self.receiver, channel)
            self._log.debug("Reporter: Subscribed to channel' : " + str(channel))

        for key, setting in self._defaults.iteritems():
            valid = False
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._defaults[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'pause':
                if str(setting).lower() in ['all', 'in', 'out', 'off']:
                    valid = True
            elif key == 'interval' or 'batchsize':
                if setting.isdigit():
                    valid = True
            else:
                continue
            if valid:
                self._settings[key] = setting
                self._log.debug("Setting " + self.name + " " + key + ": " + str(setting))
            else:
                self._log.warning("In reporter:set '%s' is not a valid setting for %s: %s" % (setting, self.name, key))

    def add(self, cargo):
        """Append data to buffer.

        data (list): node and values (eg: '[node,val1,val2,...]')

        """

        # Create a frame of data in "emonCMS format"
        f = []
        f.append(cargo.timestamp)
        f.append(cargo.nodeid)
        for i in cargo.realdata:
            f.append(i)
        if cargo.rssi:
            f.append(cargo.rssi)

        self._log.debug(str(cargo.uri) + " adding frame to buffer => "+ str(f))

        # self._log.debug(str(carg.ref) + " added to buffer =>"
        #                 + " time: " + str(carg.timestamp)
        #                 + ", node: " + str(carg.node)
        #                 + ", data: " + str(carg.data))

        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 3450 ...]]
        self.buffer.storeItem(f)

    def receiver(self, cargo):
        self.add(cargo)
    
    def run(self):
        """
        Run the reporter thread.
        Any regularly performed tasks actioned here along with flushing the buffer

        """
        
        while not self.stop:
            # Don't loop to fast
            time.sleep(0.1)
            # Action reporter tasks
            self.action()

    def action(self):
        """

        :return:
        """

        # pause output if 'pause' set to 'all' or 'out'
        if 'pause' in self._settings \
                and str(self._settings['pause']).lower() in ['all', 'out']:
            return

        # If an interval is set, check if that time has passed since last post
        if int(self._settings['interval']) \
                and time.time() - self._interval_timestamp < int(self._settings['interval']):
            return
        else:
            # Then attempt to flush the buffer
            self.flush()

    def flush(self):
        """Send oldest data in buffer, if any."""
        
        # Buffer management
        # If data buffer not empty, send a set of values
        if self.buffer.hasItems():
            max_items = int(self._settings['batchsize'])
            if max_items > self._item_limit:
                max_items = self._item_limit
            elif max_items <= 0:
                return

            databuffer = self.buffer.retrieveItems(max_items)
            retrievedlength = len(databuffer)
            if self._process_post(databuffer):
                # In case of success, delete sample set from buffer
                self.buffer.discardLastRetrievedItems(retrievedlength)
                # log the time of last succesful post
                self._interval_timestamp = time.time()

    def _process_post(self, data):
        """
        To be implemented in subclass.

        :return: True if data posted successfully and can be discarded
        """
        pass

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

"""class EmonHubEmoncmsReporter

Stores server parameters and buffers the data between two HTTP requests

"""


class EmonHubEmoncmsReporter(EmonHubReporter):

    def __init__(self, reporterName, **kwargs):
        """Initialize reporter

        """

        # Initialization
        super(EmonHubEmoncmsReporter, self).__init__(reporterName, **kwargs)

        # add or alter any default settings for this reporter
        self._defaults.update({'batchsize': 100})
        self._cms_settings = {'apikey': "", 'url': 'http://emoncms.org'}

        # This line will stop the default values printing to logfile at start-up
        self._settings.update(self._defaults)

        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250

    def set(self, **kwargs):
        """

        :param kwargs:
        :return:
        """

        super (EmonHubEmoncmsReporter, self).set(**kwargs)

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
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (setting, self.name, key))

    def _process_post(self, databuffer):
        """Send data to server."""
        
        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 250 ...]]

        if not 'apikey' in self._settings.keys() or str.__len__(self._settings['apikey']) != 32 \
                or str.lower(self._settings['apikey']) == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
            return


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

"""class EmonHubReporterInitError

Raise this when init fails.

"""


class EmonHubReporterInitError(Exception):
    pass
