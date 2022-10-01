"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import time
import logging
from configobj import ConfigObj
import json
import imp

"""class EmonHubSetup

User interface to setup the hub.

The settings attribute stores the settings of the hub. It is a
dictionary with the following keys:

        'hub': a dictionary containing the hub settings
        'interfacers': a dictionary containing the interfacers

        The hub settings are:
        'loglevel': the logging level

        interfacers are dictionaries with the following keys:
        'Type': class name
        'init_settings': dictionary with initialization settings
        'runtimesettings': dictionary with runtime settings
        Initialization and runtime settings depend on the interfacer type.

The run() method is supposed to be run regularly by the instantiater, to
perform regular communication tasks.

The check_settings() method is run regularly as well. It checks the settings
and returns True is settings were changed.

This almost empty class is meant to be inherited by subclasses specific to
each setup.

"""

class EmonHubSetup:
    def __init__(self):
        # Initialize logger
        self._log = logging.getLogger("EmonHub")

        # Initialize settings
        self.settings = None
        self.redis_found = False

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


class EmonHubFileSetup(EmonHubSetup):
    def __init__(self, filename):
        # Initialization
        super().__init__()

        self._filename = filename

        # Initialize update timestamp
        self._settings_update_timestamp = 0
        self._retry_time_interval = 5

        self.retry_msg = " Retry in " + str(self._retry_time_interval) + " seconds"

        # Make emonhub.conf available over redis for local emoncms installation
        try:
            imp.find_module('redis')
            self.redis_found = True
            self._log.info("Redis found")
            import redis
            self.r = redis.Redis(host="localhost",port=6379,db=0)
        except ImportError:
            self.redis_found = False
            self._log.info("Redis not found")

        # Initialize attribute settings as a ConfigObj instance
        try:
<<<<<<< HEAD
        
            if self._fileformat == "ConfigObj":
                self.settings = ConfigObj(filename, file_error=True)
            else:            
                with open(filename) as f:
                    self.settings = json.loads(f.read())
            
            # Translate configuration into json object and reload back to python dict
            if self.redis_found:
                jsonstr = json.dumps(self.settings)
                self.r.set("get:emonhubconf",jsonstr)
                self._log.info("emonhub conf loaded to redis")
            
=======
            self.settings = ConfigObj(filename, file_error=True)

>>>>>>> origin/master
            # Check the settings file sections
            self.settings['hub']
            self.settings['interfacers']
        except IOError as e:
            raise EmonHubSetupInitError(e)
        except SyntaxError as e:
            raise EmonHubSetupInitError(
                'Error parsing config file "%s": ' % filename + str(e))
        except KeyError as e:
            raise EmonHubSetupInitError(
                'Configuration file error - section: ' + str(e))

    def check_settings(self):
        """Check settings

        Update attribute settings and return True if modified.

        """

        # Check settings only once per second (could be extended if processing power is scarce)
        now = time.time()
        if now - self._settings_update_timestamp < 1:
            return
        # Update timestamp
        self._settings_update_timestamp = now

        # Backup settings
        settings = dict(self.settings)

        # Get settings from file
        try:
<<<<<<< HEAD
            if self._fileformat == "ConfigObj":
                self.settings.reload()
            else:            
                with open(self._filename) as f:
                    self.settings = json.loads(f.read())                
                
=======
            self.settings.reload()
>>>>>>> origin/master
        except IOError as e:
            self._log.warning('Could not get settings: %s %s', e, self.retry_msg)
            self._settings_update_timestamp = now + self._retry_time_interval
            return
        except SyntaxError as e:
            self._log.warning('Could not get settings: ' +
                              'Error parsing config file: %s %s', e, self.retry_msg)
            self._settings_update_timestamp = now + self._retry_time_interval
            return
        except Exception:
            import traceback
            self._log.warning("Couldn't get settings, Exception: %s %s",
                              traceback.format_exc(), self.retry_msg)
            self._settings_update_timestamp = now + self._retry_time_interval
            return

<<<<<<< HEAD
        # Redis interface to emonhub.conf
        # Check for configuration in set topic & apply to settings if present:
        if self.redis_found:    
            result = self.r.get("set:emonhubconf")
            if result:
                self.r.delete("set:emonhubconf");
                jsonsettings = json.loads(result)
                # 4. Merge dict with original configobj class
                self.settings.merge(jsonsettings)
                # 5. Save to conf file
                self.settings.write()
                self._log.info("emonhub conf saved from redis")
        
=======
>>>>>>> origin/master
        if self.settings != settings:
            # Reload latest settings to redis get topic if change detected:
            if self.redis_found:
                jsonstr = json.dumps(self.settings)
                self.r.set("get:emonhubconf",jsonstr)
                self._log.info("emonhub conf loaded to redis")
                
            # Check the settings file sections
            try:
                self.settings['hub']
                self.settings['interfacers']
            except KeyError as e:
                self._log.warning("Configuration file missing section: %s", e)
            else:
                return True
<<<<<<< HEAD
            
=======
>>>>>>> origin/master

"""class EmonHubSetupInitError

Raise this when init fails.

"""
class EmonHubSetupInitError(Exception):
    pass
