#!/usr/bin/python3
# EmonHubSMASolarInterfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

__author__ = 'Jo Vanvoorden'

import asyncio
import Cargo
import json
import time

from emonhub_interfacer import EmonHubInterfacer
from goodwe import Goodwe_inverter


"""class EmonHubGoodWeInterfacer

Fetch GoodWe state of charge and other variables

"""

class EmonHubGoodWeInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        super().__init__(name)

        # Interfacer specific settings
        self._template_settings = {'name': 'goodwe',
                                   'ip': None,
                                   'port': 8899,
                                   'timeout': 2,
                                   'retries': 3,
                                   'readinterval': 10.0}

        # FIXME is there a good reason to reduce this from the default of 1000? If so, document it here.
        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250


        # Fetch first reading at one interval lengths time
        self._last_time = 0
    
    def read(self):
        # Request GoodWe data at user specified interval
        if time.time() - self._last_time >= self._settings['readinterval']:
            self._last_time = time.time()

            # If URL is set, fetch the SOC
            if self._settings['ip'] != None:
                try:
                    self._inverter = asyncio.run(Goodwe_inverter.discover(self._settings['ip'], self._settings['port'], self._settings['timeout'], self._settings['retries']))
                    data = asyncio.run(self._inverter.read_runtime_data())
                except asyncio.CancelledError:
                    self._log.warning("The task %s is cancelled", self.name)
                
                self._log.debug("%s Request response: %s", self.name, data)

                names = []
                values = []

                for key in self._inverter.sensors():
                    self._log.debug("Key %s found", key.id)
                    # Check if key.id is in data object readout
                    if not key.id in data:
                        self._log.warning("Key %s not found", key.id)
                        return
                    # Check if we have a numerical response and return it
                    if isinstance(data[key.id], (int, float)):
                        names.append(key.id)
                        values.append(data[key.id])

                # Create cargo object
                c = Cargo.new_cargo()
                c.nodeid = self._settings['name']

                c.names = names
                c.realdata = values
                return c

        # return empty if not time
        return

    def set(self, **kwargs):
        for key, setting in self._template_settings.items():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._template_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'readinterval':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = float(setting)
                continue
            elif key == 'name':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = setting
                continue
            elif key == 'ip':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = setting
                continue
            elif key == 'port':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = setting
                continue
            elif key == 'timeout':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = setting
                continue
            elif key == 'retries':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)
