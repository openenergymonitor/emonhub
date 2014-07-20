#!/usr/bin/env python

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
import Queue

import emonhub_interface as ehi
import emonhub_dispatcher as ehd
import emonhub_listener as ehl
import emonhub_coder as ehc

"""class EmonHub

Monitors data inputs through EmonHubListener instances, and sends data to
target servers through EmonHubEmoncmsDispatcher instances.

Communicates with the user through an EmonHubInterface

"""


class EmonHub(object):
    
    __version__ = 'Pre-Release Development Version'
    
    def __init__(self, interface):
        """Setup an OpenEnergyMonitor emonHub.
        
        interface (EmonHubInterface): User interface to the hub.
        
        """

        # Initialize exit request flag
        self._exit = False

        # Initialize interface and get settings
        self._interface = interface
        settings = self._interface.settings

        # Logging
        self._init_logger()
        self._log.info("EmonHub %s" % self.__version__)
        self._log.info("Opening hub...")

        # Initialize dispatchers and listeners
        self._dispatchers = {}
        self._listeners = {}
        self._queue = {}
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
                # Execute run method
                l.run()
                # Read socket
                values = l.read()
                # If complete and valid data was received
                if values is not None:
                    # Place a copy of the values in a queue for each dispatcher
                    for name in self._dispatchers:
                        # discard if 'pause' set to true or to pause input only
                        if 'pause' in self._dispatchers[name]._settings \
                                and self._dispatchers[name]._settings['pause'] in \
                                ['i', 'I', 'in', 'In', 'IN', 't', 'T', 'true', 'True', 'TRUE']:
                            continue
                        self._queue[name].put(values)

            # Sleep until next iteration
            time.sleep(0.2)
         
    def close(self):
        """Close hub. Do some cleanup before leaving."""
        
        for l in self._listeners.itervalues():
            l.close()

        for d in self._dispatchers.itervalues():
            d.stop = True
        
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
        for name in self._dispatchers.keys():
            # If dispatcher is not in the settings anymore or if 'type' is omitted, delete it
            # This adds tha ability to skip creation or delete/rebuild by commenting 'type' in conf
            if name not in settings['dispatchers'] or 'type' not in settings['dispatchers'][name]:
                self._log.info("Deleting dispatcher '%s'", name)
                self._dispatchers[name].stop = True
                del(self._dispatchers[name])
        for name, dis in settings['dispatchers'].iteritems():
            # If dispatcher does not exist, create it
            if name not in self._dispatchers:
                try:
                    if not 'type' in dis:
                        continue
                    self._log.info("Creating " + dis['type'] + " '%s' ", name)
                    # Create the queue for this dispatcher
                    self._queue[name] = Queue.Queue(0)
                    # This gets the class from the 'type' string
                    dispatcher = getattr(ehd, dis['type'])(name, self._queue[name], **dis['init_settings'])
                except ehd.EmonHubDispatcherInitError as e:
                    # If dispatcher can't be created, log error and skip to next
                    self._log.error("Failed to create '" + name + "' dispatcher: " + str(e))
                    continue
                else:
                    self._dispatchers[name] = dispatcher
            # Set runtime settings
            self._dispatchers[name].set(**dis['runtime_settings'])

        # Listeners
        for name in self._listeners.keys():
            # If listener is not in the settings anymore or if 'type' is omitted, delete it
            # This adds tha ability to skip creation or delete/rebuild by commenting 'type' in conf
            if name not in settings['listeners'] or 'type' not in settings['listeners'][name]:
                self._listeners[name].close()
                self._log.info("Deleting listener '%s' ", name)
                del(self._listeners[name])
        for name, lis in settings['listeners'].iteritems():
            # If listener does not exist, create it
            if name not in self._listeners:
                try:
                    if not 'type' in lis:
                        continue
                    self._log.info("Creating " + lis['type'] + " '%s' ", name)
                    # This gets the class from the 'type' string
                    listener = getattr(ehl, lis['type'])(**lis['init_settings'])
                except ehl.EmonHubListenerInitError as e:
                    # If listener can't be created, log error and skip to next
                    self._log.error("Failed to create '" + name + "' listener: " + str(e))
                    continue
                else:
                    self._listeners[name] = listener
                setattr(listener, 'name', name)
            # Set runtime settings
            self._listeners[name].set(**lis['runtime_settings'])

        if 'nodes' in settings:
            ehc.nodelist = settings['nodes']

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

    # Logging configuration
    def _init_logger(self):
        settings = self._interface.settings
        self._log = logging.getLogger("EmonHub")
        
        if settings['hub']['console_log'] is True:
            # If this flag is provided, everything goes to sys.stderr
            loghandler = logging.StreamHandler()
        else:
            # Otherwise, rotating logging over two 5 MB files
            loghandler = logging.handlers.RotatingFileHandler(settings['hub']['logfile'],
                                                              'a', 5000 * 1024, 1)
        # Format log strings
        loghandler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(message)s'))
        self._log.addHandler(loghandler)
    
        self._set_logging_level(settings['hub']['loglevel'])
        
        
if __name__ == "__main__":

    # Command line arguments parser
    parser = argparse.ArgumentParser(description='OpenEnergyMonitor emonHub')
    # Configuration file
    parser.add_argument("--config-file", action="store",
                        help='Configuration file', default=sys.path[0]+'/emonhub.conf')
    # Logfile
    parser.add_argument('--console-log', action='store_true',
                        help='log to STDERR instead of the configured logfile')
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

    # Initialize hub interface
    try:
        interface = ehi.EmonHubFileInterface(args.config_file)
    except ehi.EmonHubInterfaceInitError as e:
        sys.exit("Configuration file not found: " + args.config_file)
 
    # Inject the console log arg into the settings, however they were loaded
    # this abstracts emonhub from having to worry about args and settings 
    interface.settings['hub']['console_log'] = args.console_log
 
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
