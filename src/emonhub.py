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

import emonhub_setup as ehs
import emonhub_dispatcher as ehd
import emonhub_listener as ehi
import emonhub_coder as ehc

"""class EmonHub

Monitors data inputs through EmonHubInterfacer instances, and sends data to
target servers through EmonHubEmoncmsDispatcher instances.

Communicates with the user through an EmonHubSetup

"""


class EmonHub(object):
    
    __version__ = 'Pre-Release Development Version'
    
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
        self._set_logging_level(settings['hub']['loglevel'])
        self._log.info("EmonHub %s" % self.__version__)
        self._log.info("Opening hub...")
        
        # Initialize dispatchers and Interfacers
        self._dispatchers = {}
        self._interfacers = {}
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
            
            # Run setup and update settings if modified
            self._setup.run()
            if self._setup.check_settings():
                self._update_settings(self._setup.settings)
            
            # For all Interfacers
            for I in self._interfacers.itervalues():
                # Execute run method
                I.run()
                # Read socket
                values = I.read()
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
        
        for I in self._interfacers.itervalues():
            I.close()

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

        # Create a place to hold buffer contents whilst a deletion & rebuild occurs
        self.temp_buffer = {}
        
        # Dispatchers
        for name in self._dispatchers.keys():
            # check init_settings against the file copy, if they are different create a back-up of buffer
            if self._dispatchers[name].init_settings != settings['dispatchers'][name]['init_settings']:
                if self._dispatchers[name].buffer._data_buffer:
                    self.temp_buffer[name]= self._dispatchers[name].buffer._data_buffer
            # Or if dispatcher is still in the settings and has a 'type' just move on to the next one
            # (This provides an ability to delete & rebuild by commenting 'type' in conf)
            elif name in settings['dispatchers'] and 'type' in settings['dispatchers'][name]:
                continue
            # Delete dispatchers if setting changed or name is unlisted or type is missing
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
                    dispatcher.init_settings = dis['init_settings']
                    # If a memory buffer back-up exists copy it over and remove the back-up
                    if name in self.temp_buffer:
                        dispatcher.buffer._data_buffer = self.temp_buffer[name]
                        del self.temp_buffer[name]
                except ehd.EmonHubDispatcherInitError as e:
                    # If dispatcher can't be created, log error and skip to next
                    self._log.error("Failed to create '" + name + "' dispatcher: " + str(e))
                    continue
                else:
                    self._dispatchers[name] = dispatcher
            # Set runtime settings
            self._dispatchers[name].set(**dis['runtimesettings'])

        # Interfacers
        for name in self._interfacers.keys():
            # check init_settings against the file copy, if they are different pass for deletion
            if self._interfacers[name].init_settings != settings['interfacers'][name]['init_settings']:
                pass
            # Or if Interfacer is still in the settings and has a 'type' just move on to the next one
            # (This provides an ability to delete & rebuild by commenting 'type' in conf)
            elif name in settings['interfacers'] and 'type' in settings['interfacers'][name]:
                continue
            self._interfacers[name].close()
            self._log.info("Deleting interfacer '%s' ", name)
            del(self._interfacers[name])
        for name, I in settings['interfacers'].iteritems():
            # If interfacer does not exist, create it
            if name not in self._interfacers:
                try:
                    if not 'type' in I:
                        continue
                    self._log.info("Creating " + I['type'] + " '%s' ", name)
                    # This gets the class from the 'type' string
                    interfacer = getattr(ehi, I['type'])(**I['init_settings'])
                    interfacer.init_settings = I['init_settings']
                except ehi.EmonHubInterfacerInitError as e:
                    # If interfacer can't be created, log error and skip to next
                    self._log.error("Failed to create '" + name + "' interfacer: " + str(e))
                    continue
                else:
                    self._interfacers[name] = interfacer
                setattr(interfacer, 'name', name)
            # Set runtime settings
            self._interfacers[name].set(**I['runtimesettings'])

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
        
if __name__ == "__main__":

    # Command line arguments parser
    parser = argparse.ArgumentParser(description='OpenEnergyMonitor emonHub')

    # Configuration file
    parser.add_argument("--config-file", action="store",
                        help='Configuration file', default=sys.path[0]+'/../conf/emonhub.conf')
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

    # Initialize hub setup
    try:
        setup = ehs.EmonHubFileSetup(args.config_file)
    except ehs.EmonHubSetupInitError as e:
        logger.critical(e)
        sys.exit("Configuration file not found: " + args.config_file)
 
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
