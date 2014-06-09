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

import emonhub_buffer as ehb
  
"""class EmonHubDispatcher

Stores server parameters and buffers the data between two HTTP requests

This class is meant to be inherited by subclasses specific to their 
destination server.

"""


class EmonHubDispatcher(object):

    def __init__(self, dispatcherName, bufferMethod="memory", **kwargs):
        """Create a server data buffer initialized with server settings."""
        
        # Initialize logger
        self._log = logging.getLogger("EmonHub")

        # Initialize variables
        self._settings = {}
        self.name = ''
        
        # Create underlying buffer implementation
        self.buffer = ehb.getBuffer(bufferMethod)(dispatcherName, **kwargs)
        
        self._log.info("Set up dispatcher '%s' (buffer: %s)"
                       % (dispatcherName, bufferMethod))
        
    def set(self, **kwargs):
        """Update settings.
        
        **kwargs (dict): settings to be modified.
        
        url (string): eg: 'http://localhost/emoncms' or 'http://emoncms.org' (trailing slash optional)
        apikey (string): API key with write access
        active (string): whether the dispatcher is active (True/False)
        
        """
       
        for key, value in kwargs.iteritems():
            # Strip trailing slash
            if key == 'url':
                value = value.rstrip('/')
                                    
            self._settings[key] = value

    def add(self, data):
        """Append data to buffer.

        data (list): node and values (eg: '[node,val1,val2,...]')

        """
       
        if self._settings['active'] == 'False':
            return
        
        # Timestamp = now
        t = round(time.time(), 2)

        self._log.debug("Append to '" + self.name +
                        "' buffer => time: " + str(t)
                        + ", data: " + str(data))
        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 3450 ...]]
        item = [t]
        item += data
        self.buffer.storeItem(item)

    def _send_data(self, data):
        """Send data to server.

        data (list): node and values (eg: '[node,val1,val2,...]')
        time (int): timestamp, time when sample was recorded

        return True if data sent correctly
        
        To be implemented in subclass.

        """
        pass

    def flush(self):
        """Send oldest data in buffer, if any."""
        
        # Buffer management
        # If data buffer not empty, send a set of values
        if self.buffer.hasItems():
            if 'maxItemsPerPost' in self._settings.keys():
                max_items = int(self._settings['maxItemsPerPost'])
            else:
                max_items = 250

            databuffer = self.buffer.retrieveItems(max_items)
            if self._send_data(databuffer):
                # In case of success, delete sample set from buffer
                self.buffer.discardLastRetrievedItem()

"""class EmonHubEmoncmsDispatcher

Stores server parameters and buffers the data between two HTTP requests

"""


class EmonHubEmoncmsDispatcher(EmonHubDispatcher):

    def _send_data(self, databuffer):
        """Send data to server."""
        
        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 250 ...]]

        data_string = json.dumps(databuffer, separators=(',', ':'))

        self._log.debug("Data string: " + data_string)
        
        # Prepare URL string of the form
        # http://domain.tld/emoncms/input/bulk.json?apikey=12345
        # &data=[[0,10,82,23],[5,10,82,23],[10,10,82,23]]
        # &sentat=15' (requires emoncms >= 8.0)

        # time that the request was sent at
        sentat = int(time.time())

        # Send data to server
        self._log.info("Sending: " + self._settings['url'] + "/input/bulk" +
                       " | data="+data_string+"&sentat="+str(sentat))

        # The Develop branch of emoncms allows for the sending of the apikey in the post
        # body, this should be moved from the url to the body as soon as this is widely
        # adopted
        req = urllib2.Request(
            self._settings['url']+'/input/bulk'+'.json?apikey='+self._settings['apikey'],
            "data="+data_string+"&sentat="+str(sentat))

        try:
            response = urllib2.urlopen(req, timeout=60)
        except urllib2.HTTPError as e:
            self._log.warning("Couldn't send to server, HTTPError: " +
                              str(e.code))
        except urllib2.URLError as e:
            self._log.warning("Couldn't send to server, URLError: " +
                              str(e.reason))
        except httplib.HTTPException:
            self._log.warning("Couldn't send to server, HTTPException")
        except Exception:
            import traceback
            self._log.warning("Couldn't send to server, Exception: " +
                              traceback.format_exc())
        else:
            reply = response.read()
            if reply == 'ok':
                self._log.debug("Receipt acknowledged with '" + reply + "' from " + self._settings['url'])
                return True
            else:
                self._log.warning("Send failure: wanted 'ok' but got "+reply)
