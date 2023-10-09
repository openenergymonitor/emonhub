#!/usr/bin/python3
# EmonHubHeatmiserInterfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

__author__ = 'Dan Conlon'

import sys
import time
import traceback
import socket
import json
import Cargo
from urllib.error import HTTPError
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubHeatmiserInterfacer

Fetch metrics from Heatmiser Neo thermostats

"""

class EmonHubHeatmiserInterfacer(EmonHubInterfacer):

    def __init__(self, name, neohub_host, neohub_port=4242, pollinterval=60, nodeid=29):
        """Initialize interfacer"""

        # Initialization
        super().__init__(name)

        self._NodeName = name
        self._NodeId = int(nodeid)
        self._neohub_host = neohub_host
        self._neohub_port = int(neohub_port)
        self._poll_interval = int(pollinterval)
        
        self._next_poll_time = None
        self._socket = None
        

    def close(self):
        if self._socket:
            self._log.info("Closing connection to NeoHub")
            self._socket.close()
            self._socket = None
        
    def _set_poll_timer(self, seconds):
        self._next_poll_time = time.time() + seconds

    def _is_it_time(self):
        if not self._next_poll_time: # First time loop
            return True
            
        return time.time() > self._next_poll_time

    # Override base _process_rx code from emonhub_interfacer
    def _process_rx(self, rxc):
        if not rxc:
            return False

        return rxc

    # Override base read code from emonhub_interfacer
    def read(self):
        """Read data from neohub"""

        # Wait until we are ready to fetch
        if not self._is_it_time():
            return
        
        cargo = None
        
        try:
            self._connect_to_neohub()
    
            cargo = self._fetch_from_neohub()
            
            # Poll timer reset after successful fetch
            self._set_poll_timer(self._poll_interval)

        except Exception as err2:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self._log.error(err2)
            self._log.debug(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            self.close()
            self._set_poll_timer(10) # Retry in 10 seconds
            
        return cargo
        
    def _connect_to_neohub(self):
        # Nothing to do if already connected
        if self._socket:
            return
            
        # Create a TCP socket 
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(30)
        
        # Connect to NeoHub
        self._socket.connect((self._neohub_host, self._neohub_port))
        
            
    def _fetch_from_neohub(self):
        # Send request
        self._socket.send(bytes(json.dumps({'GET_LIVE_DATA':0}) + "\0\r", 'UTF-8'))

        # Receive data
        received = ""
        while True:
            buf = self._socket.recv(1024).decode('UTF-8')
            received += buf
            if "\0" in received:
                received = received.rstrip("\0")
                break
            if len(buf) == 0:
                break

        # Decode JSON response
        response = json.loads(received)

        # Extract data for each device in the NeoHub response
        names = []
        values = []
        for device in response['devices']:
            log_text = ""
            zone_name = device['ZONE_NAME']
            for key in ['OFFLINE', 'HEAT_ON', 'SET_TEMP', 'ACTUAL_TEMP']:
                if key not in device:
                    self._log.error("key '%s' not found in [%s] for %s", key, ', '.join(device.keys()), zone_name)
                    continue
                label = zone_name + ' ' + key
                names.append(label)
                values.append(device[key])
                log_text += " " + key + ":" + str(device[key]) 
                
            self._log.info("%s - %s", zone_name, log_text)
                
            
        # Cargo object for returning values
        c = Cargo.new_cargo()
        c.rawdata = None
        c.realdata = values
        c.names = names
        c.nodeid = self._NodeId
        c.nodename = self._NodeName            

        return c

           

 
