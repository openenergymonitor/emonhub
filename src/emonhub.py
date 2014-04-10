#!/usr/bin/env python

"""

  This code is released under the GNU Affero General Public License.
  
  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import sys
import time
import logging, logging.handlers
import signal
import argparse
import pprint

import emonhub_interface as ehi
import emonhub_dispatcher as ehd
import emonhub_listener as ehl

"""class EmonHub

Monitors data inputs through EmonHubListener instances, and sends data to
target servers through EmonHubEmoncmsDispatcher instances.

Communicates with the user through an EmonHubInterface

"""
class EmonHub(object):
    
    __version__ = 'v1.0.0'
    
    def __init__(self, interface):
        """Setup an OpenEnergyMonitor emonHub.
        
        interface (EmonHubInterface): User interface to the hub.
        
        """

        # Initialize exit request flag
        self._exit = False

        # Initialize interface and get settings
        self._interface = interface
        settings = self._interface.settings
        
        # Initialize logging
        self._log = logging.getLogger("EmonHub")
        self._set_logging_level(settings['hub']['loglevel'])
        self._log.info("EmonHub %s" % self.__version__)
        self._log.info("Opening hub...")
        
        # Initialize dispatchers and listeners
        self._dispatchers = {}
        self._listeners = {}
        self._update_settings(settings)
        
    def run(self):
        """Launch the hub.
        
        Monitor the COM port and process data.
        Check settings on a regular basis.

        """

       # Set signal handler to catch SIGINT and shutdown gracefully
        signal.signal(signal.SIGINT, self._sigint_handler)
        
        # Until asked to stop
        while not self._exit:
            
            # Run interface and update settings if modified
            self._interface.run()
            if self._interface.check_settings():
                self._update_settings(self._interface.settings)
            
            # For all listeners
            for l in self._listeners.itervalues():
                # Execture run method
                l.run()
                # Read socket
                values = l.read()
                # If complete and valid data was received
                if values is not None:
                    # Add data to dispatcher
                    for b in self._dispatchers.itervalues():
                        b.add(values)
            
            # For all dispatchers
            for b in self._dispatchers.itervalues():
                # Send one set of values to server
                b.flush()

            # Sleep until next iteration
            time.sleep(0.2);
         
    def close(self):
        """Close hub. Do some cleanup before leaving."""
        
        for l in self._listeners.itervalues():
            l.close()
        
        self._log.info("Exiting hub...")
        logging.shutdown()

    def _sigint_handler(self, signal, frame):
        """Catch SIGINT (Ctrl+C)."""
        
        self._log.debug("SIGINT received.")
        # hub should exit at the end of current iteration.
        self._exit = True

    def _update_settings(self, settings):
        """Check settings and update if needed."""
        
        # EmonHub Logging level
        self._set_logging_level(settings['hub']['loglevel'])
        
        # Dispatchers
        for name, buf in settings['dispatchers'].iteritems():
            # If dispatcher does not exist, create it
            if name not in self._dispatchers:
                # This gets the class from the 'type' string
                self._log.info("Creating dispatcher %s", name)

                self._dispatchers[name] = \
                    getattr(ehd, buf['type'])(name, **buf['init_settings'])
            # Set runtime settings
            self._dispatchers[name].set(**buf['runtime_settings'])
        # If existing dispatcher is not in settings anymore, delete it
        for name in self._dispatchers:
            if name not in settings['dispatchers']:
                self._log.info("Deleting dispatcher %s", name)
                del(self._dispatchers[name])

        # Listeners
        for name, lis in settings['listeners'].iteritems():
            # If listener does not exist, create it
            if name not in self._listeners:
                self._log.info("Creating listener %s", name)
                try:
                    # This gets the class from the 'type' string
                    listener = getattr(ehl, lis['type'])(**lis['init_settings'])
                except ehl.EmonHubListenerInitError as e:
                    # If listener can't be created, log error and skip to next
                    self._log.error(e)
                    continue
                else:
                    self._listeners[name] = listener
            # Set runtime settings
            self._listeners[name].set(**lis['runtime_settings'])
        # If existing listener is not in settings anymore, delete it
        for name in self._listeners:
            if name not in settings['listeners']:
                self._listeners[name].close()
                self._log.info("Deleting listener %s", name)
                del(self._listeners[name])

    def _set_logging_level(self, level):
        """Set logging level.
        
        level (string): log level name in 
        ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
        """
        
        # Check level argument is valid
        try:
            loglevel = getattr(logging, level)
        except AttributeError:
            self._log.error('Logging level %s invalid' % level)
            return False
        
        # Change level if different from current level
        if loglevel != self._log.getEffectiveLevel():
            self._log.setLevel(level)
            self._log.info('Logging level set to %s' % level)

if __name__ == "__main__":

    # Command line arguments parser
    parser = argparse.ArgumentParser(description='OpenEnergyMonitor emonHub')
    # Configuration source: config file or emoncms
    settings_group = parser.add_mutually_exclusive_group()
    settings_group.add_argument("--config-file", action="store", help='Configuration file')
    settings_group.add_argument("--config-emoncms", action="store", help='URL to local emoncms')
    # Logfile
    parser.add_argument('--logfile', action='store', type=argparse.FileType('a'),
        help='path to optional log file (default: log to Standard error stream STDERR)')
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
        print('emonHub %s' % EmonHub.__version__)
        sys.exit()
    
    # Logging configuration
    logger = logging.getLogger("EmonHub")
    if args.logfile is None:
        # If no path was specified, everything goes to sys.stderr
        loghandler = logging.StreamHandler()
    else:
        # Otherwise, rotating logging over two 5 MB files
        # If logfile is supplied, argparse opens the file in append mode,
        # this ensures it is writable
        # Close the file for now and get its path
        args.logfile.close()
        loghandler = logging.handlers.RotatingFileHandler(args.logfile.name,
                                                       'a', 5000 * 1024, 1)
    # Format log strings
    loghandler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(loghandler)

    # Initialize hub interface
    # Emoncms GUI interface
    if args.config_emoncms:
        try:
            interface = ehi.EmonHubEmoncmsInterface(args.config_emoncms)
        except ehi.EmonHubInterfaceInitError as e:
            logger.critical(e)
            sys.exit("Invalid emoncms URL: "+ args.config_emoncms)
    # Text config file
    else:
        # Default filename if none specified
        if args.config_file is None:
            args.config_file = sys.path[0]+'/emonhub.conf'
        try:
            interface = ehi.EmonHubFileInterface(args.config_file)
        except ehi.EmonHubInterfaceInitError as e:
            logger.critical(e)
            sys.exit("Configuration file not found: "+ args.config_file)
 
    # If in "Show settings" mode, print settings and exit
    if args.show_settings:
        interface.check_settings()
        pprint.pprint(interface.settings)
    
    # Otherwise, create, run, and close EmonHub instance
    else:
        try:
            hub = EmonHub(interface)
        except Exception as e:
            sys.exit("Could not start EmonHub: " + str(e))
        else:
            hub.run()
            # When done, close hub
            hub.close()
 
