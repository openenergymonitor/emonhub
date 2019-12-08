#!/usr/bin/python3
# EmonHubBMWInterfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

# Inspiration taken from https://github.com/edent/BMW-i-Remote/tree/master/python

__author__ = 'Stuart Pittaway'

import time
import sys
import traceback
import json
import os.path
import requests
import Cargo
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubBMWInterfacer

Monitors BMW i3 car metrics via BMW API

"""

class EmonHubBMWInterfacer(EmonHubInterfacer):

    ROOT_URL = "https://www.bmw-connecteddrive.co.uk"
    USER_AGENT = "MCVApp/1.5.2 (iPhone; iOS 9.1; Scale/2.00)"
    _chargingSystemStatus = "NOCHARGING"

    def __init__(self, name, bmwapiusername='', bmwapipassword='', tempcredentialfile='/tmp/bmwcredentials.json', timeinverval=600, duringchargetimeinterval=60, nodeid=28):
        """Initialize interfacer"""

        # Initialization
        super().__init__(name)

        self._NodeId = int(nodeid)
        self._Username = bmwapiusername
        self._Password = bmwapipassword

        self._time_inverval = int(timeinverval)
        self._time_inverval_during_charge = int(duringchargetimeinterval)
        self._reset_duration_timer()

        self._NodeName = name
        self._TempCredentialFile = tempcredentialfile
        self._first_time_loop = True

        if os.path.exists(self._TempCredentialFile):  # FIXME race condition
            with open(self._TempCredentialFile, "r") as cf:
                credentials = json.load(cf)

            self._AccessToken = credentials["access_token"]
            self._TokenExpiry = credentials["token_expiry"]
            self._log.info("Loaded credentials from cache")
        else:
            self.obtainCredentials()

    def obtainCredentials(self):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self.USER_AGENT
        }

        data = {
            "client_id": "dbf0a542-ebd1-4ff0-a9a7-55172fbfce35",
            "redirect_uri": "https://www.bmw-connecteddrive.com/app/default/static/external-dispatch.html",
            "response_type": "token",
            "scope": "authenticate_user fupo",
            "username": self._Username,
            "password": self._Password
        }

        r = requests.post("https://customer.bmwgroup.com/gcdm/oauth/authenticate", allow_redirects=False, data=data, headers=headers)
        #We expect a 302 reply (redirect)

        if r.status_code == 302:
            # We want the access_token, token_type and expires_in from the Location querystring parameters
            location = r.headers["Location"]

            if location.startswith("https://www.bmw-connecteddrive.com/app/default/static/external-dispatch.html"):
                # Parse the URL and querystring
                d = {}

                parts = location.split("&")
                for word in parts[1:]:
                    values = word.split("=")
                    d[values[0]] = values[1]
                    #self._log.debug("word=" + word)

                access_token = parts[0].split("#")
                for word in access_token[1:]:
                    values = word.split("=")
                    d[values[0]] = values[1]  # FIXME dict comprehension

                # We should now have a dictionary object with three entries
                # token_type, access_token, expires_in

                self._AccessToken = d["access_token"]
                self._TokenExpiry = time.time() + float(d["expires_in"])
                self.saveCredentials()

            else:
                self._log.error("locationHeader=" + location)
                self._log.error("Location URL is different from expected")

        else:
            # Throw exception if API call failed
            r.raise_for_status()
            self._log.error("Obtained invalid response from authenticate API request")

    def saveCredentials(self):
        """
        Save current state to the JSON file.
        """
        credentials = {
            #"auth_basic": self.auth_basic,
            "access_token": self._AccessToken,
            "token_expiry": self._TokenExpiry
        }
        # Open a file for writing
        with open(self._TempCredentialFile, "w") as credentials_file:
            json.dump(credentials, credentials_file, indent=4)

        self._log.info("Cached credentials to " + self._TempCredentialFile)

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
        if self._chargingSystemStatus == "CHARGINGACTIVE":
            # Charging in progress
            waittime = self._time_inverval_during_charge
        else:
            # Not charging
            waittime = self._time_inverval

        return int(duration_of_delay) > waittime

    def call(self, path, post_data=None):
        """
        Call the API at the given path.
        Argument should be relative to the API base URL, e.g:

            print c.call('/user/vehicles/')
        If a dictionary 'post_data' is specified, the request will be
        a POST, otherwise a GET.
        """
        if time.time() > self._TokenExpiry:
            self.obtainCredentials()

        headers = {"Authorization": "Bearer " + self._AccessToken,
                   "User-Agent": self.USER_AGENT}

        #self._log.debug("headers=" + str(headers))

        if post_data is None:
            r = requests.get(self.ROOT_URL + path, headers=headers)
        else:
            r = requests.post(self.ROOT_URL + path, headers=headers, data=post_data)

        #Raise exception if problem with request
        r.raise_for_status()
        return r.json()

    # Override base _process_rx code from emonhub_interfacer
    def _process_rx(self, rxc):
        if not rxc:
            return False

        return rxc

    # Override base read code from emonhub_interfacer
    def read(self):
        """Read data from BMW API"""

        #Wait until we are ready to read from inverter
        if not self._is_it_time() and not self._first_time_loop:
            return

        self._reset_duration_timer()

        self._first_time_loop = False

        try:
            #self._log.debug("Entering read section")

            #https://www.bmw-connecteddrive.co.uk/api/me/vehicles/v2?all=true
            vehicles = self.call('/api/me/vehicles/v2?all=true')

            myvehicle = vehicles[0]

            #Returns a dictionary object containing...
            #[{u'supportedChargingModes': [u'AC_LOW', u'DC'], u'hasNavi': True,
            #  u'modelName': u'i3 94REX', u'bodyType': u'Hatchback', u'series': u'I',
            #  u'brand': u'BMWi', u'basicType': u'I3 94REX', u'vin': u'WBY1Z11111V222222',
            #  u'hasSunRoof': False, u'steering': u'RIGHT', u'licensePlate': u'AA11ABC',
            #  u'dcOnly': True, u'driveTrain': u'BEV_REX', u'doorCount': 4, u'maxFuel': u'8.5', u'hasRex': True}]

            self._log.debug("modelName='" + myvehicle["modelName"] + "' VIN='" + myvehicle["vin"] + "'")

            vin = myvehicle["vin"]

            dynamic = self.call('/api/vehicle/dynamic/v1/' + vin + "?offset=0")

            #Report efficiency of driving (not currently used by this program)
            #efficiency = self.call('/api/vehicle/efficiency/v1/' + vin)
            #self._log.debug("efficiency=" + str(efficiency))

            attributesMap = dynamic["attributesMap"]

            names = []
            values = []

            for key in ['battery_size_max', 'beMaxRangeElectricKm', 'beMaxRangeElectricMile', 'beRemainingRangeElectricKm', 'beRemainingRangeElectricMile', 'beRemainingRangeFuelKm', 'beRemainingRangeFuelMile', 'chargingLevelHv', 'fuelPercent', 'kombi_current_remaining_range_fuel', 'mileage', 'remaining_fuel', 'soc_hv_percent']:
                if key in attributesMap:
                    names.append(key)
                    values.append(float(attributesMap[key]))

            # Store if the car is charging or not
            self._chargingSystemStatus = attributesMap["chargingSystemStatus"]

            # CHARGINGACTIVE

            names.append("ChargingActive")
            if self._chargingSystemStatus == "CHARGINGACTIVE":
                values.append(1)
            else:
                values.append(0)

            self._log.debug("chargingSystemStatus=" + self._chargingSystemStatus)

            #u'unitOfElectricConsumption = u'mls/kWh'
            #u'unitOfCombustionConsumption = u'mpg'
            #u'unitOfEnergy':u'kWh'
            #u'unitOfLength':u'mls',

            #self._log.debug("Building cargo")
            c = Cargo.new_cargo()
            c.rawdata = None
            c.realdata = values
            c.names = names

            # This appears to cause problems for emonCMS and the emonHUB as it wont forward
            # events which are in the past
            #Ensure we use the datetime from the API call as this only changes every few hours
            #when the car is NOT charging
            c.timestamp = float(attributesMap["updateTime_converted_timestamp"]) / 1000

            c.nodeid = self._NodeId
            c.nodename = self._NodeName

            #self._log.debug("Returning cargo")
            return c

        except Exception as err2:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self._log.error(err2)
            self._log.error(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
