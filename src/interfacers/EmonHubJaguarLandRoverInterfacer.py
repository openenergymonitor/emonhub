#!/usr/bin/python3
# EmonHubJaguarLandRoverInterfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

# Inspiration taken from Stuart Pittaway's EmonHubBMWInterfacer. With thanks
# to @ardevd for jlrpy python library for interacting with the JLR's API.

__author__ = 'Dan Conlon'

import jlrpy
import sys
import time
import traceback
import Cargo
from urllib.error import HTTPError
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubJaguarLandRoverInterfacer

Monitors car metrics via Jaguar Land Rover API

"""

class EmonHubJaguarLandRoverInterfacer(EmonHubInterfacer):

    def __init__(self, name, jlrusername='', jlrpassword='', timeinverval=600, duringchargetimeinterval=60, nodeid=28):
        """Initialize interfacer"""

        # Initialization
        super().__init__(name)

        self._NodeId = int(nodeid)
        self._Username = jlrusername
        self._Password = jlrpassword

        self._time_inverval = int(timeinverval)
        self._time_inverval_during_charge = int(duringchargetimeinterval)
        self._reset_duration_timer()

        self._NodeName = name
        self._first_time_loop = True
        self._chargingStatus = "UNKNOWN"
        self._jlrConnection = None

    def close(self):
        """Close"""
        return

    def _reset_duration_timer(self):
        """Reset timer to current date/time"""
        self._last_time_reading = time.time()

    def _is_it_time(self):
        """Checks to see if the duration has expired

        Return true or false

        """
        duration_of_delay = time.time() - self._last_time_reading

        # CHARGINGACTIVE/NOCHARGING
        if self._chargingStatus == "CHARGING":
            # Charging in progress
            waittime = self._time_inverval_during_charge
        else:
            # Not charging
            waittime = self._time_inverval

        return int(duration_of_delay) > waittime

    def _create_jlr_connection(self):
        """Creates a new jlrpy connection """
        try:
            self._jlrConnection = jlrpy.Connection(self._Username, self._Password)
        except HTTPError as err:
            # Give a helpful message when username/password incorrect
            if err.code == 403:
                raise Exception('Incorrect username or password') from err
            else:
                raise

    # Override base _process_rx code from emonhub_interfacer
    def _process_rx(self, rxc):
        if not rxc:
            return False

        return rxc

    # Override base read code from emonhub_interfacer
    def read(self):
        """Read data from JLR API"""

        # Wait until we are ready to fetch
        if not self._is_it_time() and not self._first_time_loop:
            return

        self._reset_duration_timer()

        self._first_time_loop = False

        try:
            # Create connection in the loop so network errors at startup don't prevent interfacer creation
            if self._jlrConnection is None:
                self._create_jlr_connection()
            
            # Select the first vehicle in the account
            vehicle = self._jlrConnection.vehicles[0]
            self._log.info("Fetching status of VIN %s", vehicle.vin)

            statusResponse = vehicle.get_status()

            coreStatusList = statusResponse['vehicleStatus']['coreStatus']
            evStatusList = statusResponse['vehicleStatus']['evStatus']
            statusList = coreStatusList + evStatusList
            statusDict = {d['key']: d['value'] for d in statusList}

            names = []
            values = []

            # TODO: add FUEL_LEVEL_PERC
            for key in ['ODOMETER_MILES','EV_STATE_OF_CHARGE','EV_RANGE_ON_BATTERY_MILES','EV_RANGE_ON_BATTERY_KM','EV_CHARGING_RATE_SOC_PER_HOUR']:
                names.append(key)
                if key in statusDict:
                    self._log.info("%s = %s", key, statusDict[key])
                    try:
                        values.append(float(statusDict[key]))
                    except ValueError:
                        values.append(-1)
                else:
                    values.append(-1)

            # OpenEVSE expects charge remaining time in seconds
            names.append('EV_SECONDS_TO_FULLY_CHARGED')
            if 'EV_MINUTES_TO_FULLY_CHARGED' in statusDict:
                self._log.info("%s = %s", 'EV_MINUTES_TO_FULLY_CHARGED', statusDict['EV_MINUTES_TO_FULLY_CHARGED'])
                values.append(float(statusDict['EV_MINUTES_TO_FULLY_CHARGED']) * 60)
            else:
                values.append(-1)

            # Store if the car is charging or not
            if 'EV_CHARGING_STATUS' in statusDict:
                self._log.info("%s = %s", 'EV_CHARGING_STATUS', statusDict['EV_CHARGING_STATUS'])
                self._chargingStatus = statusDict['EV_CHARGING_STATUS']
            names.append("EV_CHARGING_STATUS")
            if self._chargingStatus == "CHARGING":
                values.append(1)
            else:
                values.append(0)

            c = Cargo.new_cargo()
            c.rawdata = None
            c.realdata = values
            c.names = names

            c.nodeid = self._NodeId
            c.nodename = self._NodeName

            return c

        except Exception as err2:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self._log.error(err2)
            self._log.error(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
