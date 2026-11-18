"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import time
import logging
from configobj import ConfigObj

# Descriptions of settings, shown in the emoncms config editor.
# Plain strings only, read without importing this module.
settings_info = {
    "hub": {
        "loglevel": "Detail written to emonhub.log: DEBUG, INFO, WARNING, ERROR or CRITICAL. Applied without a restart.",
        "autoconf": "Adds known nodes to [nodes] from templates in available.conf when they first send data. 1 on, 0 off. Restart emonhub after changing.",
        "use_syslog": "Also sends log messages to syslog when set to yes. Read at start-up, so restart emonhub after changing.",
        "log_backup_count": "Number of old log files kept when emonhub.log is rotated. Default 1.",
        "log_max_bytes": "Size at which emonhub.log is rotated, in bytes. Default 5120000."
    },
    "node": {
        "nodename": "Name used for this node's inputs in emoncms, in place of the node ID.",
        "nodeids": "Only used in autoconf templates in available.conf to match node IDs. No effect here.",
        "datalength": "Only used in autoconf templates in available.conf to match data length. No effect here."
    },
    "rx": {
        "names": "Input names, one per value, in the order the values are received.",
        "datacodes": "Datacode for each value, giving its binary type. Total size must match the received data length or the frame is discarded.",
        "datacode": "Single datacode used for every value when datacodes is not set.",
        "scales": "Multiplier for each value, e.g. 0.01 turns 2345 into 23.45. Count must match the number of values.",
        "scale": "Single multiplier used for every value when scales is not set.",
        "units": "Unit for each value. Not read by emonhub at present, kept for reference and node templates.",
        "whitening": "Undoes radio data whitening by XOR with 0x55 on each byte. Set to 1 to enable."
    },
    "tx": {
        "names": "Names of the values sent to this node. Not read by emonhub at present, kept for reference.",
        "datacodes": "Datacode for each value sent, giving its binary type.",
        "datacode": "Single datacode used for every value sent when datacodes is not set.",
        "scales": "Divisor for each value before sending, the reverse of the rx scales.",
        "scale": "Single divisor used for every value sent when scales is not set.",
        "units": "Unit for each value. Not read by emonhub at present, kept for reference."
    }
}

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

    @property
    def filename(self):
        return self._filename

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
