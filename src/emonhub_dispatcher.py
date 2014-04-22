"""

  This code is released under the GNU Affero General Public License.
  
  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import urllib2, httplib
import time
import logging
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
        
        # Create underlying buffer implementation
        self.buffer = getattr(
            ehb, 
            ehb.AbstractBuffer.bufferMethodMap[bufferMethod])(dispatcherName,
                                                               **kwargs)
        
        self._log.info ("Set up dispatcher '%s' (buffer: %s)"
                        % (dispatcherName, bufferMethod))
        
    def set(self, **kwargs):
        """Update settings.
        
        **kwargs (dict): settings to be modified.
        
        domain (string): domain name (eg: 'domain.tld')
        path (string): emoncms path with leading slash (eg: '/emoncms')
        apikey (string): API key with write access
        active (string): whether the dispatcher is active (True/False)
        
        """

        for key, value in kwargs.iteritems():
            self._settings[key] = value

    def add(self, data):
        """Append data to buffer.

        data (list): node and values (eg: '[node,val1,val2,...]')

        """
       
        if self._settings['active'] == 'False':
            return
        
        # Timestamp = now
        t = round(time.time(),2)
        
        self._log.debug("Server " + 
                           self._settings['domain'] + self._settings['path'] + 
                           " -> buffer data: " + str(data) + 
                           ", timestamp: " + str(t))
               
        self.buffer.storeItem([t, data])

    def _send_data(self, data, time):
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
        if (self.buffer.hasItems()):
            time, data = self.buffer.retrieveItem()
            self._log.debug("Server " + 
                           self._settings['domain'] + self._settings['path'] + 
                           " -> send data: " + str(data) + 
                           ", timestamp: " + str(time))
            if self._send_data(data, time):
                # In case of success, delete sample set from buffer
                self.buffer.discardLastRetrievedItem()

"""class EmonHubEmoncmsDispatcher

Stores server parameters and buffers the data between two HTTP requests

"""
class EmonHubEmoncmsDispatcher(EmonHubDispatcher):

    def _send_data(self, data, timestamp):
        """Send data to server."""
        
        # Prepare data string with the values in data buffer
        data_string = '['
        # WIP: currently, only one set of values (one timsetamp) is sent
        # so bulk mode is not really useful yet
        for (timestamp, data) in [(timestamp, data)]:
            data_string += '['
            data_string += str(int(round(timestamp-time.time())))
            for sample in data:
                data_string += ','
                data_string += str(sample)
            data_string += '],'
        # Remove trailing comma and close bracket
        data_string = data_string[0:-1]+']'

        self._log.debug("Data string: " + data_string)
        
        # Prepare URL string of the form
        # 'http://domain.tld/emoncms/input/bulk.json?apikey=
        # 12345&data=[[-10,10,1806],[-5,10,1806],[0,10,1806]]
        # &offset=0' (requires emoncms >= 8.0)
        url_string = self._settings['protocol'] + self._settings['domain'] + \
                     self._settings['path'] + "/input/bulk.json?apikey=" + \
                     self._settings['apikey'] + "&data=" + data_string + \
                     "&offset=0"

        # Send data to server
        self._log.info("Sending to " + 
                          self._settings['domain'] + self._settings['path'])
                          
        try:
            result = urllib2.urlopen(url_string, timeout=60)
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
            response = result.readline()
            if (response == 'ok'):
                self._log.debug("Send ok")
                return True
            else:
                self._log.warning("Send failure: wanted 'ok' but got "+response)
        
