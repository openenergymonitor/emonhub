#!/usr/bin/env python3

"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""


import sys
import time
import logging
import logging.handlers
import signal
import argparse
import pprint
import glob
import os
import getpass
from collections import defaultdict

import emonhub_setup as ehs
import emonhub_coder as ehc
import emonhub_interfacer as ehi
import emonhub_http_api as ehapi
import emonhub_auto_conf as eha
from interfacers import *

# this namespace and path
namespace = sys.modules[__name__]
path = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

# scan interfacers directory and import all interfacers
for f in glob.glob(path + "/interfacers/*.py"):
    name = f.replace(".py", "").replace(path + "/interfacers/", "")
    if name != "__init__":
        # print "Loading: " + name
        setattr(ehi, name, getattr(getattr(namespace, name), name))
del name

"""class EmonHub

Monitors data inputs through EmonHubInterfacer instances,
and (currently) sends data to
target servers through EmonHubEmoncmsReporter instances.

Controlled by the user via EmonHubSetup

"""

class EmonHub:

    __version__ = "v? missing version file"
    vpath = path.replace("/src","");
    if os.path.exists(vpath+"/version.txt"):
        f = open(vpath+"/version.txt", "r")
        __version__ = "v"+f.read().strip()

    def __init__(self, setup):
        """Setup an OpenEnergyMonitor emonHub.

        Interface (EmonHubSetup): User interface to the hub.

        """
        # Initialize exit request flag
        self._exit = False

        # Initialize setup and get settings
        self._setup = setup
        settings = self._setup.settings

        # Initialize logging
        self._log = logging.getLogger("EmonHub")
        self._set_logging_level('INFO', False)
        self._log.info("EmonHub %s", self.__version__)
        self._log.info("Opening hub...")
        self._log.info("Running as user: "+str(getpass.getuser()))
        
        # Initialize Interfacers
        self._interfacers = {}
        
        self._http_api = False

        # Update settings
        self._update_settings(settings)
        
        # Load available
        try:
            self.autoconf = eha.EmonHubAutoConf(settings)
            eha.available = self.autoconf.available
            eha.auto_conf_enabled = self.autoconf.enabled
        except eha.EmonHubAutoConfError as e:
            logger.error(e)
            sys.exit("Unable to load available.conf")
        
    def run(self):
        """Launch the hub.

        Monitor the interfaces and process data.
        Check settings on a regular basis.

        """
        # Initialize http api
        try:
            self._http_api = ehapi.EmonHubHTTPApi(self._setup.settings,self._interfacers)
            self._http_api.start()
        except Exception as e:
            logger.critical(e)

        # Set signal handler to catch SIGINT or SIGTERM and shutdown gracefully
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialise thread restart counters
        restart_count = defaultdict(int)

        # Until asked to stop
        while not self._exit:

            # Run setup and update settings if modified
            self._setup.run()
            if self._setup.check_settings():
                self._update_settings(self._setup.settings)

            # Auto conf populate nodelist 
            if eha.auto_conf_enabled and ehc.nodelist != self._setup.settings['nodes']:
                self._log.info("Nodelist has been updated by an interfacer, updating config file");
                self._setup.settings['nodes'] = ehc.nodelist
                self._setup.settings.write()

            # For all Interfacers
            kill_list = []
            for I in self._interfacers.values():
                # Check threads are still running
                if not I.is_alive():
                    kill_list.append(I.name) # <-avoid modification of iterable within loop

                # Read each interfacers pub channels
                for pub_channel in I._settings['pubchannels']:

                    if pub_channel in I._pub_channels and len(I._pub_channels[pub_channel]) > 0:
                        # POP cargo item (one at a time)
                        cargo = I._pub_channels[pub_channel].pop(0)

                        # Post to each subscriber interface
                        for sub_interfacer in self._interfacers.values():
                            # For each subscriber channel
                            for sub_channel in sub_interfacer._settings['subchannels']:
                                # If channel names match
                                if sub_channel == pub_channel:
                                    # APPEND cargo item
                                    sub_interfacer._sub_channels.setdefault(sub_channel, []).append(cargo)

            # ->avoid modification of iterable within loop
            for name in kill_list:
                self._log.warning("%s thread is dead.", name)

                # The following should trigger a restart ... unless the
                # interfacer is also removed from the settings table.
                del self._interfacers[name]

                # Trigger restart by calling update settings
                self._log.warning("Attempting to restart thread %s (thread has been restarted %d times...)", name, restart_count[name])
                restart_count[name] += 1
                self._update_settings(self._setup.settings)

            # Sleep until next iteration
            time.sleep(0.2)

    def close(self):
        """Close hub. Do some cleanup before leaving."""

        self._log.info("Exiting hub...")

        for I in self._interfacers.values():
            I.stop = True
            I.join()

        self._http_api.stop();
        
        self._log.info("Exit completed")

    def _signal_handler(self, signal, frame):
        """Catch fatal signals like SIGINT (Ctrl+C) and SIGTERM (service stop)."""

        self._log.debug("Signal %d received.", signal)
        # hub should exit at the end of current iteration.
        self._exit = True

    def _update_settings(self, settings):
        """Check settings and update if needed."""

        # EmonHub Logging level
        if 'loglevel' in settings['hub']:
            self._set_logging_level(settings['hub']['loglevel'])
        else:
            self._set_logging_level()

        if 'log_backup_count' in settings['hub']:
            for handler in self._log.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.backupCount = int(settings['hub']['log_backup_count'])
                    self._log.info("Logging backup count set to %d", handler.backupCount)
        if 'log_max_bytes' in settings['hub']:
            for handler in self._log.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.maxBytes = int(settings['hub']['log_max_bytes'])
                    self._log.info("Logging max file size set to %d bytes", handler.maxBytes)

        # Interfacers
        interfacers_to_delete = []
        for name in self._interfacers:
            # Delete interfacers if not listed or have no 'Type' in the settings without further checks
            # (This also provides an ability to delete & rebuild by commenting 'Type' in conf)
            if name in settings['interfacers'] and 'Type' in settings['interfacers'][name]:
                try:
                    # test for 'init_settings' and 'runtime_setting' sections
                    settings['interfacers'][name]['init_settings']
                    settings['interfacers'][name]['runtimesettings']
                except Exception as e:
                    # If interfacer's settings are incomplete, continue without updating
                    self._log.error("Unable to update '%s' configuration: %s", name, e)
                    continue
                else:
                    # check init_settings against the file copy, if they are the same move on to the next
                    if self._interfacers[name].init_settings == settings['interfacers'][name]['init_settings']:
                        continue
            # Delete interfacers if setting changed or name is unlisted or Type is missing
            self._log.info("Deleting interfacer '%s'", name)
            self._interfacers[name].stop = True
            interfacers_to_delete.append(name)

        for name in interfacers_to_delete:
            del self._interfacers[name]

        for name, I in settings['interfacers'].items():
            # If interfacer does not exist, create it
            if name not in self._interfacers:
                try:
                    if 'Type' not in I:
                        continue
                    self._log.info("Creating %s '%s'", I['Type'], name)
                    # This gets the class from the 'Type' string
                    interfacer = getattr(ehi, I['Type'])(name, **I['init_settings'])
                    interfacer.set(**I['runtimesettings'])
                    interfacer.init_settings = I['init_settings']
                    interfacer.start()
                except ehi.EmonHubInterfacerInitError as e:
                    # If interfacer can't be created, log error and skip to next
                    self._log.error("Failed to create '%s' interfacer: %s", name, e)
                    continue
                except Exception as e:
                    # If interfacer can't be created, log error and skip to next
                    self._log.error("Unable to create '%s' interfacer: %s", name, e)
                    continue
                else:
                    self._interfacers[name] = interfacer
            else:
                # Otherwise just update the runtime settings if possible
                if 'runtimesettings' in I:
                    self._interfacers[name].set(**I['runtimesettings'])

        if 'nodes' in settings:
            ehc.nodelist = settings['nodes']

    def _set_logging_level(self, level='WARNING', log=True):
        """Set logging level.

        level (string): log level name in
        ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')

        """

        # Ensure "level" is all upper case
        level = level.upper()

        # Check level argument is valid
        try:
            loglevel = getattr(logging, level)
        except AttributeError:
            self._log.error('Logging level %s invalid', level)
            return False
        except Exception as e:
            self._log.error('Logging level %s', e)
            return False

        # Change level if different from current level
        if loglevel != self._log.getEffectiveLevel():
            self._log.setLevel(level)
            if log:
                self._log.info('Logging level set to %s', level)
        return True


if __name__ == "__main__":

    # Command line arguments parser
    parser = argparse.ArgumentParser(description='OpenEnergyMonitor emonHub')

    # Configuration file
    parser.add_argument("--config-file", action="store",
                        help='Configuration file', default=sys.path[0] + '/../conf/emonhub.conf')
    # Log file
    parser.add_argument('--logfile', action='store', type=argparse.FileType('a'),
                        help='Log file (default: log to Standard error stream STDERR)')
    # Show settings
    parser.add_argument('--show-settings', action='store_true',
                        help='show settings and exit (for debugging purposes)')
    # Show version
    parser.add_argument('--version', action='store_true',
                        help='display version number and exit')
    # Parse arguments
    args = parser.parse_args()

    # Display version number and exit
    if args.version:
        print('emonHub', EmonHub.__version__)
        sys.exit()

    # Logging configuration
    logger = logging.getLogger("EmonHub")
    if args.logfile:
        # If path was given, rotating logging over two 5 MB files
        # If logfile is supplied, argparse opens the file in append mode,
        # this ensures it is writable
        # Close the file for now and get its path
        args.logfile.close()
        # These maxBytes and backupCount defaults can be overridden in the config file.
        loghandler = logging.handlers.RotatingFileHandler(args.logfile.name,
                                                          maxBytes=5000 * 1024,
                                                          backupCount=1)
    else:
        # Otherwise, if no path was specified, everything goes to sys.stderr
        loghandler = logging.StreamHandler()
    # Format log strings
    loghandler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)-8s %(threadName)-10s %(message)s'))

    logger.addHandler(loghandler)

    # Initialize hub setup
    try:
        setup = ehs.EmonHubFileSetup(args.config_file)
    except ehs.EmonHubSetupInitError as e:
        logger.critical(e)
        sys.exit("Unable to load configuration file: " + args.config_file)
      
    if 'use_syslog' in setup.settings['hub']:
        if setup.settings['hub']['use_syslog'] == 'yes':
            syslogger = logging.handlers.SysLogHandler(address='/dev/log')
            syslogger.setFormatter(logging.Formatter(
                'emonHub[%(process)d]: %(levelname)-8s %(threadName)-10s %(message)s'))
            logger.addHandler(syslogger)
    
    # If in "Show settings" mode, print settings and exit
    if args.show_settings:
        setup.check_settings()
        pprint.pprint(setup.settings)

    # Otherwise, create, run, and close EmonHub instance
    else:
        try:
            hub = EmonHub(setup)
        except Exception as e:
            sys.exit("Could not start EmonHub: " + str(e))
        else:
            hub.run()
            # When done, close hub
            hub.close()
