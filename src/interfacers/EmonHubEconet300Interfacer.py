#!/usr/bin/python3
# EmonHubEconet300Interfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

__author__ = 'Dan Conlon'

import sys
import time
import traceback
import requestse
import Cargo
from emonhub_interfacer import EmonHubInterfacer
from requests.auth import HTTPBasicAuth


"""class EmonHubEconet300Interfacer
Fetch metrics from a Plum ecoNET 300 bridge (used by Grant Aerona heat pumps). This interfacer
periodically polls the bridge HTTP API and maps returned fields (which are nested in different
sections) into a flat payload with descriptive names.
"""

# Known parameters for Grant Aerona R290 heat pumps. Each entry maps a human-friendly
# name to a tuple (location, key) representing the location of the parameter in the JSON
# returned by the ecoNET-300 API. Parameters have been detemrined by community reverse
# engineering and experimentation (see Sources below).
#
# Sources:
# - @GSV3MiaC  https://community.openenergymonitor.org/t/new-heat-pump-grant-r290-hot-water-advice/28254/38
# - @LeeNuss   https://github.com/LeeNuss/ecoNET-300-Home-Assistant-Integration/tree/1.2.0-a-ecomax360-1
PARAMS_GRANT_AERONA_R290 = {
    'circulation_pump_stopped':     ('informationParams', '11'),  # 1 = pump stopped, 0 = pump running
    'target_flow_temp':             ('informationParams', '12'),
    'is_space_heating':             ('informationParams', '13'),  # 0 is HW, 1 is CH
    'flow_temp':                    ('informationParams', '14'),  # duplicated at 24 and data 14, 24, 91
    'return_temp':                  ('informationParams', '15'),  # duplicated at 25
    'compressor_frequency':         ('informationParams', '21'),
    'fan_speed':                    ('informationParams', '22'),  # duplicated at data 1219
    'ambient_temp_heatpump':        ('informationParams', '23'),
    'no_heat_demanded':             ('informationParams', '26'),  # 1 - no heat demanded, 0 - heat demanded
    'dhw_temp':                     ('informationParams', '61'),
    'buffer_temp_top':              ('informationParams', '71'),  # buffer top temp probe, duplicated at 92 and 243
    'circuit1_target_flow_temp':    ('informationParams', '93'),
    'circuit2_measured_temp':       ('informationParams', '101'), # circuit2 temp probe
    'circuit3_measured_temp':       ('informationParams', '111'), # circuit3 temp probe
    'touchscreen_firmware_version': ('informationParams', '181'),
    'controller_firmware_version':  ('informationParams', '182'),
    'uid':                          ('informationParams', '184'),
    'serial_number':                ('informationParams', '185'),
    'input_power':                  ('informationParams', '211'), # not working
    'output_power':                 ('informationParams', '212'), # not working
    'cop':                          ('informationParams', '221'), # not working
    'scop':                         ('informationParams', '222'), # not working
    'dhw_work_mode':                ('data', '119'),              # 0 is off, 1 is on, 2 is scheduled
    'dhw_setpoint':                 ('data', '103'),
    'dhw_hysteresis':               ('data', '104'),
    'dhw_boost':                    ('data', '115'),
    'dhw_legionella_setpoint':      ('data', '136'),              # Legionella protection temperature (60-80°C)
    'dhw_legionella_day':           ('data', '137'),              # Legionella protection day of week (0-6)
    'dhw_legionella_hour':          ('data', '138'),              # Legionella protection hour (0-23)
    'circuit1_work_mode':           ('data', '236'),              # 0 is off, 1 is day, 2 is night, 3 is scheduled
    'circuit1_day_setpoint':        ('data', '238'),
    'circuit1_night_setpoint':      ('data', '239'),
    'circuit1_hysteresis':          ('data', '240'),
    'circuit1_weather_curve':       ('data', '273'),
    'circuit1_weather_curve_shift': ('data', '275'),
    'summer_on_temp':               ('data', '702'),              # Outdoor temp threshold to activate summer mode (26-30°C)
    'summer_off_temp':              ('data', '703'),              # Outdoor temp threshold to deactivate summer mode (0-26°C)
    'flow_rate':                    ('data', '1211'),
    'silent_mode_level':            ('data', '1385'),             # 0 = level 1, 2 = level 2
    'silent_mode':                  ('data', '1386'),             # 0 = off, 2 = scheduled
    'touchscreen_temp_correction':  ('data', '10413'), # to check
    'weather_sensor_temp':          ('curr', 'TempWthr'),
    'touchscreen_ambient_temp':     ('curr', 'Circuit1thermostat'), # only if C1 has touchscreen set as its thermostat
    'system_pressure':              ('tilesParams', 76)
}

class EmonHubEconet300Interfacer(EmonHubInterfacer):

    def __init__(self, name, host, username, password, pollinterval, nodeid=30):
        """Initialize the Econet300 interfacer.

        Parameters
        - name: string used as node name
        - host: hostname/IP of ecoNET-300 bridge
        - username/password: basic auth credentials for bridge HTTP API
        - pollinterval: seconds between successful polls
        - nodeid: node id to use in generated Cargo (default 30)
        """

        # Call base class initializer
        super().__init__(name)

        self._NodeName = name
        self._NodeId = int(nodeid)
        self._host = host
        self._username = username
        self._password = password
        self._poll_interval = int(pollinterval)

        # Timestamp for next scheduled poll (None => first loop should run)
        self._next_poll_time = None

        # Only the Grant Aerona R290 is supported for now
        self._params_map = PARAMS_GRANT_AERONA_R290

    def close(self):
        return None
        
    def _set_poll_timer(self, seconds):
        """Schedule the next poll `seconds` from now."""
        self._next_poll_time = time.time() + seconds

    def _is_it_time(self):
        """Return True if the next poll time has been reached (or unset). On the first run
        `_next_poll_time` will be None so the method returns True to allow an immediate poll.
        """
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
        """Periodically poll the bridge and return a `Cargo` with metrics. This enforces the poll
        interval, calls `_fetch_data()` to perform HTTP requests and mapping, and handles
        transient errors by scheduling a short retry.
        """

        # Wait until we are ready to fetch
        if not self._is_it_time():
            return

        cargo = None

        try:
            # Perform HTTP fetch and mapping
            cargo = self._fetch_data()

            # Poll timer reset after successful fetch
            self._set_poll_timer(self._poll_interval)

        except Exception as err2:
            # Log the detailed traceback for debugging
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self._log.error(err2)
            self._log.debug(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))

            # Retry shortly in case of errors
            self._set_poll_timer(10) # Retry in 10 seconds

        return cargo

    def _fetch_data(self):
        """Fetch JSON from the bridge and map known parameters. The bridge exposes multiple
        endpoints and nested structures; `_params_map` tells this method where to look for
        each metric.
        """
        # The mappings below require two endpoints: '/econet/regParams' and '/econet/editParams', which
        # together contain the values referenced by `_params_map`.
        regParams  = self._econet_http_request("/econet/regParams")
        editParams = self._econet_http_request("/econet/editParams")

        data = {}

        # Iterate the mapping and extract values from the appropriate nested locations, handling missing
        # fields gracefully so one missing metric won't stop the whole poll.
        for (name, (location, key) ) in self._params_map.items():
            try:
                if location == 'curr':
                    value = regParams['curr'][key]
                elif location == 'tilesParams':
                    value = regParams['tilesParams'][key][0][0][0]
                elif location == 'informationParams':
                    value = editParams['informationParams'][key][1][0][0]
                elif location == 'data':
                    value = editParams['data'][key]['value']
                else:
                    raise Exception(f"Unknown param location {location}")
                data[name] = value
            except Exception as e:
                self._log.warning(f"Unable to retrieve {name}: {e.__class__.__name__} {e}")

        # Cargo object for returning values
        c = Cargo.new_cargo()
        c.rawdata = None
        c.realdata = list(data.values())
        c.names = list(data.keys())
        c.nodeid = self._NodeId
        c.nodename = self._NodeName

        return c

    def _econet_http_request(self, path):
        """Perform an authenticated GET against the bridge and return parsed JSON. Raises an Exception
        on non-200 responses or if the response body cannot be decoded as JSON.
        """
        basic = HTTPBasicAuth(self._username, self._password)

        r = requests.get("http://" + self._host + path, auth=basic)

        if r.status_code != 200:
            raise Exception(f"Couldn't fetch data ({r.status_code})")
        
        try:
            body = r.json()
            return body
        except Exception as e:
            raise Exception(f"Invalid data from path: {r.content}")