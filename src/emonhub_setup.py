"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import time
import logging
from configobj import ConfigObj

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

        # Initialize attribute settings as a ConfigObj instance
        try:
            self.settings = ConfigObj(filename, file_error=True)

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
        if now - self._settings_update_timestamp < 60:
            return
        # Update timestamp
        self._settings_update_timestamp = now

        # Backup settings
        settings = dict(self.settings)

        # Get settings from file
        try:
            self.settings.reload()
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

        if self.settings != settings:
            # Check the settings file sections
            try:
                self.settings['hub']
                self.settings['interfacers']
            except KeyError as e:
                self._log.warning("Configuration file missing section: %s", e)
            else:
                return True

"""class EmonHubSetupInitError

Raise this when init fails.

"""
class EmonHubSetupInitError(Exception):
    pass
