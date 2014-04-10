"""

  This code is released under the GNU Affero General Public License.
  
  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import urllib2
import time
import logging
import csv
import urlparse
from configobj import ConfigObj

"""class EmonHubInterface

User interface to communicate with the hub.

The settings attribute stores the settings of the hub. It is a
dictionnary with the following keys:

        'hub': a dictionary containing the hub settings
        'listeners': a dictionary containing the listeners
        'dispatchers': a dictionary containing the dispatchers

        The hub settings are:
        'loglevel': the logging level
        
        Listeners and dispatchers are dictionaries with the folowing keys:
        'type': class name
        'init_settings': dictionary with initialization settings
        'runtime_settings': dictionary with runtime settings
        Initialization and runtime settings depend on the listener and
        dispatcher type.

The run() method is supposed to be run regularly by the instanciater, to
perform regular communication tasks.

The check_settings() method is run regularly as well. It checks the settings 
and returns True is settings were changed.

This almost empty class is meant to be inherited by subclasses specific to
each user interface.

"""
class EmonHubInterface(object):

    def __init__(self):
        
        # Initialize logger
        self._log = logging.getLogger("EmonHub")
        
        # Initialize settings
        self.settings = None

    def run(self):
        """Run in background. 
        
        To be implemented in child class.

        """
        pass

    def check_settings(self):
        """Check settings
        
        Update attribute settings and return True if modified.
        
        To be implemented in child class.
        
        """
    
    def get_settings(self):
        """Get settings
        
        Returns None if settings couldn't be obtained.

        To be implemented in child class.
        
        """
        pass

class EmonHubEmoncmsInterface(EmonHubInterface):

    def __init__(self, local_url='http://localhost/emoncms'):
        """Initialize emoncms interface

        local_url (string): URL to local emoncms server

        """
        
        # Initialization
        super(EmonHubEmoncmsInterface, self).__init__()

        # Initialize local server settings
        url = urlparse.urlparse(local_url)
        self._local_protocol = url.scheme + '://'
        self._local_domain = url.netloc
        self._local_path = url.path 

        # Initialize update timestamps
        self._status_update_timestamp = 0
        self._settings_update_timestamp = 0
        self._retry_time_interval = 60

        # Check local emoncms URL is valid
        try:
            # Dummy time request
            result = urllib2.urlopen(self._local_protocol +
                                     self._local_domain +
                                     self._local_path +
                                     "/time/local.json")
        
        except Exception:
            import traceback
            raise EmonHubInterfaceInitError("Failure while connecting to " +
                 local_url + ":\n" + traceback.format_exc())

        # Check settings
        self.check_settings()

    def run(self):
        """Run in background. 
        
        Update raspberry_pi running status.
        
        """
        
        # Update status every second
        now = time.time()
        if (now - self._status_update_timestamp > 1):
            # Update "running" status to inform emoncms the script is running
            self._hub_running()
            # "Thanks for the status update. You've made it crystal clear."
            self._status_update_timestamp = now
            
    def check_settings(self):
        """Check settings
        
        Update attribute settings and return True if modified.
        
        """
        
        # Check settings only once per second
        now = time.time()
        if (now - self._settings_update_timestamp < 1):
            return
        # Update timestamp
        self._settings_update_timestamp = now
        
        # Get settings using emoncms API
        try:
            result = urllib2.urlopen(self._local_protocol +
                                     self._local_domain +
                                     self._local_path +
                                     "/raspberrypi/get.json")
            result = result.readline()
            # result is of the form
            # {"userid":"1","sgroup":"210",...,"remoteprotocol":"http:\\/\\/"}
            result_array = result[1:-1].split(',')
            # result is now of the form
            # ['"userid":"1"',..., '"remoteprotocol":"http:\\/\\/"']
            emoncms_s = {}
            # For each setting, separate key and value
            for s in result_array:
                # We can't just use split(':') as there can be ":" inside 
                # a value (eg: "http://")
                s_split = csv.reader([s], delimiter=':').next() 
                emoncms_s[s_split[0]] = s_split[1].replace("\\","")

        except Exception:
            import traceback
            self._log.warning("Couldn't get settings, Exception: " + 
                traceback.format_exc())
            self._settings_update_timestamp = now + self._retry_time_interval
            return
        
        settings = {}
        
        # Format EmonHub settings
        settings['hub'] = {'loglevel': 'DEBUG'} # Stubbed until implemented
            
        # RFM2Pi listener
        settings['listeners'] = {'RFM2Pi': {}}
        settings['listeners']['RFM2Pi'] = \
            {'type': 'EmonHubRFM2PiListener', 
            'init_settings': {'com_port': '/dev/ttyAMA0'},
            'runtime_settings': {}}
        for item in ['sgroup', 'frequency', 'baseid', 'sendtimeinterval']:
            settings['listeners']['RFM2Pi']['runtime_settings'][item] = \
                emoncms_s[item]

        # Emoncms servers
        settings['dispatchers'] = {'emoncms_local': {}, 'emoncms_remote': {}}
        # Local
        settings['dispatchers']['emoncms_local'] = \
            {'type': 'EmonHubEmoncmsDispatcher',
            'init_settings': {},
            'runtime_settings': {}}
        settings['dispatchers']['emoncms_local']['runtime_settings'] = \
            {'protocol': self._local_protocol,
            'domain': self._local_domain,
            'path': self._local_path,
            'apikey': emoncms_s['apikey'],
            'active': 'True'}
        # Remote
        settings['dispatchers']['emoncms_remote'] = \
            {'type': 'EmonHubEmoncmsDispatcher',
            'init_settings': {},
            'runtime_settings': {}}
        settings['dispatchers']['emoncms_remote']['runtime_settings'] = \
            {'protocol': emoncms_s['remoteprotocol'],
            'domain': emoncms_s['remotedomain'],
            'path': emoncms_s['remotepath'],
            'apikey': emoncms_s['remoteapikey'],
            'active': emoncms_s['remotesend']}

        # Return True if settings modified
        if settings != self.settings:
            self.settings = settings
            return True

    def _hub_running(self):
        """Update "script running" status."""
        
        try:
            result = urllib2.urlopen(self._local_protocol +
                                     self._local_domain +
                                     self._local_path +
                                     "/raspberrypi/setrunning.json") 
        except Exception:
            import traceback
            self._log.warning(
                "Couldn't update \"running\" status, Exception: " + 
                traceback.format_exc())

class EmonHubFileInterface(EmonHubInterface):

    def __init__(self, filename):
        
        # Initialization
        super(EmonHubFileInterface, self).__init__()

        # Initialize update timestamp
        self._settings_update_timestamp = 0
        self._retry_time_interval = 60

        # Initialize attribute settings as a ConfigObj instance
        try:
            self.settings = ConfigObj(filename, file_error=True)
        except IOError as e:
            raise EmonHubInterfaceInitError(e)
        except SyntaxError as e:
            raise EmonHubInterfaceInitError( \
                'Error parsing config file \"%s\": ' % filename + str(e))

    def check_settings(self):
        """Check settings
        
        Update attribute settings and return True if modified.
        
        """
        
        # Check settings only once per second
        now = time.time()
        if (now - self._settings_update_timestamp < 1):
            return
        # Update timestamp
        self._settings_update_timestamp = now
        
        # Backup settings
        settings = dict(self.settings)
        
        # Get settings from file
        try:
            self.settings.reload()
        except IOError as e:
            self._log.warning('Could not get settings: ' + str(e))
            self._settings_update_timestamp = now + self._retry_time_interval
            return
        except SyntaxError as e:
            self._log.warning('Could not get settings: ' + 
                              'Error parsing config file: ' + str(e))
            self._settings_update_timestamp = now + self._retry_time_interval
            return
        except Exception:
            import traceback
            self._log.warning("Couldn't get settings, Exception: " + 
                traceback.format_exc())
            self._settings_update_timestamp = now + self._retry_time_interval
            return
        
        if self.settings != settings:
            return True

"""class EmonHubInterfaceInitError

Raise this when init fails.

"""
class EmonHubInterfaceInitError(Exception):
    pass

