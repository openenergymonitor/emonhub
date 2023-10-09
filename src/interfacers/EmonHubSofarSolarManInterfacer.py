#!/usr/bin/python3
# EmonHubSofarSolarManInterfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

__author__ = 'Dan Conlon'

import sys
import time
import traceback
import Cargo
from pysolarmanv5 import PySolarmanV5
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubSofarSolarManInterfacer

Fetch metrics from Sofar inverter via SolarMan WiFi dongle

"""

class EmonHubSofarSolarManInterfacer(EmonHubInterfacer):

    def __init__(self, name, solarman_host, solarman_sn, pollinterval, nodeid=30):
        """Initialize interfacer"""

        # Initialization
        super().__init__(name)

        self._NodeName = name
        self._NodeId = int(nodeid)
        self._solarman_host = solarman_host
        self._solarman_sn = int(solarman_sn)
        self._poll_interval = int(pollinterval)

        self._next_poll_time = None
        self._sm = None

        self._registers = [
          ("pv1_voltage", 0.1), #0x0006
          ("pv1_current", 0.01), #0x0007
          ("pv2_voltage", 0.1), #0x0008
          ("pv2_current", 0.01), #0x0009
          ("pv1_power", 10), #0x000A
          ("pv2_power", 10), #0x000B
          ("output_active_power", 10), #0x000c
          ("output_reactive_power", 10), #0x000d
          ("grid_frequency", 0.01), #0x000e
          ("l1_voltage", 0.1), #0x000f
          ("l1_current", 0.01), #0x0010
          ("l2_voltage", 0.1), #0x0011
          ("l2_current", 0.01), #0x0012
          ("l3_voltage", 0.1), #0x0013
          ("l3_current", 0.01), #0x0014
          ("total_production", 1), #0x0015
          ("total_production", 1), #0x0016
          ("total_gen_time", 1), #0x0017
          ("total_gen_time", 1), #0x0018
          ("today_production", 10), #0x0019
          ("today_gen_time", 1), #0x001A
          ("module_temperature", 1), #0x001B
          ("inner_temperature", 1), #0x001C
        ]

    def close(self):
        self._sm = None
        return None
        
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
        """Read data from solarman"""

        # Wait until we are ready to fetch
        if not self._is_it_time():
            return

        cargo = None

        try:
            self._connect_to_solarman()

            cargo = self._fetch_from_solarman()

            # Poll timer reset after successful fetch
            self._set_poll_timer(self._poll_interval)

        except Exception as err2:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self._log.error(err2)
            self._log.debug(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            self.close()
            self._set_poll_timer(10) # Retry in 10 seconds

        return cargo

    def _connect_to_solarman(self):
        # Nothing to do if already connected
        if self._sm:
            return

        # Create connection

        self._sm = PySolarmanV5(self._solarman_host, self._solarman_sn, port=8899, mb_slave_id=1)

    def _fetch_from_solarman(self):
        stats = {}
        response = self._sm.read_holding_registers(register_addr=0x0006, quantity=23)
        for (name, ratio), value in zip(self._registers, response):
            if name in stats:
                # large values stored in two registers
                stats[name] = stats[name]*65536  + (value * ratio)
            else:
                stats[name] = value * ratio


        # Cargo object for returning values
        c = Cargo.new_cargo()
        c.rawdata = None
        c.realdata = stats.values()
        c.names = stats.keys()
        c.nodeid = self._NodeId
        c.nodename = self._NodeName

        return c
