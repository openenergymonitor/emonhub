#!/usr/bin/python3
# EmonHubEconet300Interfacer released for use by OpenEnergyMonitor project
# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

__author__ = 'Dan Conlon'

import sys
import time
import traceback
import requests
import Cargo
from emonhub_interfacer import EmonHubInterfacer
from requests.auth import HTTPBasicAuth


"""class EmonHubEconet300Interfacer
Fetch metrics from a Plum ecoNET 300 bridge (used by Grant Aerona heat pumps). This interfacer
periodically polls the bridge HTTP API and maps returned fields (which are nested in different
sections) into a flat payload with descriptive names.
"""

# Known parameters for Grant Aerona R290 heat pumps (ecoMAX360i controller). Each entry maps a
# human-friendly name to a tuple (location, key) representing the location of the parameter in the
# JSON returned by the ecoNET-300 API:
#
#   'informationParams' - /econet/editParams ['informationParams'][key][1][0][0]  (read-only values)
#   'data'              - /econet/editParams ['data'][key]['value']               (settings)
#   'curr'              - /econet/regParams  ['curr'][key]
#   'tilesParams'       - /econet/regParams  ['tilesParams'][key][0][0][0]
#
# Not every installation has every parameter: which circuits exist, whether they are weather
# compensated and whether DHW is enabled all change which keys the bridge returns. Missing keys are
# logged once and then skipped, so it's fine for this table to cover all configurations.
#
# Finding parameter names: the firmware name of each 'data' key is in editParams ['data'][key]['name']
# (e.g. 'Circuit2CurveRadiator'). English names, units and enum values for informationParams,
# editable params, tiles and alarm codes come from the translation table the econet24 web UI loads
# (endpoint found in the bridge's controller.js); 'ver' is the touchscreen firmware version and
# 'regName' the controller, as shown in /econet/sysParams:
#
#   curl -X POST -H 'Accept: json' --data 'ver=S024.24_1.22&client=114&lang=&regName=ecoMAX360i' \
#       https://www.econet24.com/service/getETtranslations/
#
# In that file 'informationParamN' is informationParams key N, and 'editableParamN' is data key N.
#
# Sources:
# - Plum econet24 translation table, as above (firmware S024.24, Oct 2026)
# - @GSV3MiaC  https://community.openenergymonitor.org/t/new-heat-pump-grant-r290-hot-water-advice/28254/38
# - @LeeNuss   https://github.com/LeeNuss/ecoNET-300-Home-Assistant-Integration/tree/1.2.0-a-ecomax360-1
# - @LeeNuss   https://github.com/LeeNuss/econext-gateway/blob/main/docs/PARAMETERS.md
PARAMS_GRANT_AERONA_R290 = {
    # Heat pump
    'no_heat_demanded':             ('informationParams', '11'),  # demand: 0 = heating, non-zero = no heat demanded (1 = cooling, 2 = none)
    'target_flow_temp':             ('informationParams', '12'),
    'is_space_heating':             ('informationParams', '13'),  # 3-way valve: 0 is HW, 1 is CH
    'flow_temp':                    ('informationParams', '14'),  # duplicated at 24 and data 14, 24, 91
    'return_temp':                  ('informationParams', '15'),  # duplicated at 25
    'compressor_frequency':         ('informationParams', '21'),
    'fan_speed':                    ('informationParams', '22'),  # duplicated at data 1219
    'ambient_temp_heatpump':        ('informationParams', '23'),
    'circulation_pump_stopped':     ('informationParams', '26'),  # main circulation pump: 0 = running, 1 = stopped
    'input_power':                  ('informationParams', '211'), # kW, controller estimate
    'output_power':                 ('informationParams', '212'), # kW, controller estimate
    'cooling_power':                ('informationParams', '213'), # kW
    'cop':                          ('informationParams', '221'), # not equal to output_power / input_power
    'scop':                         ('informationParams', '222'),
    'serial_number':                ('informationParams', '185'),
    'hp_work_mode':                 ('data', '1133'),             # AxenWorkState: 0 = off, 1 = on, 2 = scheduled
    'heat_cool_mode':               ('data', '1268'),             # 0 = cooling, 1 = heating, 2 = auto
    'season_mode':                  ('data', '162'),              # workState2 bits: 1 = summer, 2 = auto, 4 = winter (6 seen in auto during winter)
    'summer_on_temp':               ('data', '702'),              # Outdoor temp threshold to activate summer mode (15-30°C)
    'summer_off_temp':              ('data', '703'),              # Outdoor temp threshold to deactivate summer mode (0-16°C)
    'flow_rate':                    ('data', '1211'),             # l/min
    'silent_mode_level':            ('data', '1385'),             # 0 = level 1, 2 = level 2
    'silent_mode':                  ('data', '1386'),             # 0 = off, 2 = scheduled
    'weather_sensor_temp':          ('curr', 'TempWthr'),
    'system_pressure':              ('tilesParams', 76),

    # Buffer and backup heater
    'buffer_temp_top':              ('informationParams', '71'),  # buffer top temp probe, duplicated at 92 and 243
    'buffer_temp_bottom':           ('informationParams', '72'),
    'buffer_target_temp':           ('informationParams', '73'),
    'backup_heater':                ('informationParams', '74'),  # 0 = off, 1 = on

    # Domestic hot water (only present if DHW is enabled on the controller)
    'dhw_temp':                     ('informationParams', '61'),
    'dhw_heater':                   ('informationParams', '63'),  # 0 = off, 1 = on
    'dhw_circulation_pump':         ('informationParams', '64'),  # 0 = off, 1 = on
    'dhw_work_mode':                ('data', '119'),              # 0 is off, 1 is on, 2 is scheduled
    'dhw_setpoint':                 ('data', '103'),
    'dhw_hysteresis':               ('data', '104'),
    'dhw_boost':                    ('data', '115'),
    #'dhw_legionella_setpoint':      ('data', '136'),              # Legionella protection temperature (60-80°C)
    #'dhw_legionella_day':           ('data', '137'),              # Legionella protection day of week (0-6)
    #'dhw_legionella_hour':          ('data', '138'),              # Legionella protection hour (0-23)

    # Circuit 1 (work modes: 0 is off, 1 is day, 2 is night, 3 is scheduled)
    'circuit1_target_flow_temp':    ('informationParams', '93'),
    'circuit1_pump':                ('informationParams', '94'),  # 0 = off, 1 = on
    'circuit1_thermostat_signal':   ('informationParams', '95'),  # 0 = heat, 1 = no heat
    'circuit1_work_mode':           ('data', '236'),
    'circuit1_day_setpoint':        ('data', '238'),
    'circuit1_night_setpoint':      ('data', '239'),
    'circuit1_hysteresis':          ('data', '240'),
    'circuit1_fixed_flow_temp':     ('data', '261'),              # only with fixed regulation
    'circuit1_weather_curve':       ('data', '273'),              # only with weather regulation
    'circuit1_weather_curve_shift': ('data', '275'),              # only with weather regulation
    'touchscreen_ambient_temp':     ('curr', 'Circuit1thermostat'), # only if C1 has touchscreen set as its thermostat
    'touchscreen_temp_correction':  ('data', '10413'), # to check

    # Circuit 2
    'circuit2_measured_temp':       ('informationParams', '101'), # circuit2 temp probe
    'circuit2_target_flow_temp':    ('informationParams', '102'),
    'circuit2_pump':                ('informationParams', '103'), # 0 = off, 1 = on
    'circuit2_mixer_pump':          ('informationParams', '104'), # 0 = off, 1 = on
    'circuit2_mixer_valve':         ('informationParams', '105'), # % open
    'circuit2_thermostat_signal':   ('informationParams', '106'), # 0 = heat, 1 = no heat
    'circuit2_work_mode':           ('data', '286'),
    'circuit2_day_setpoint':        ('data', '288'),
    'circuit2_night_setpoint':      ('data', '289'),
    'circuit2_hysteresis':          ('data', '290'),
    'circuit2_min_flow_temp':       ('data', '291'),
    'circuit2_max_flow_temp':       ('data', '292'),
    'circuit2_night_reduction':     ('data', '312'),              # K, applied to the flow temperature at night
    'circuit2_fixed_flow_temp':     ('data', '311'),              # only with fixed regulation
    'circuit2_weather_curve':       ('data', '323'),              # only with weather regulation
    'circuit2_weather_curve_shift': ('data', '325'),              # only with weather regulation
    'circuit2_room_temp':           ('curr', 'Circuit2thermostatTemp'),

    # Circuit 3
    'circuit3_measured_temp':       ('informationParams', '111'), # circuit3 temp probe
    'circuit3_target_flow_temp':    ('informationParams', '112'),
    'circuit3_pump':                ('informationParams', '113'), # 0 = off, 1 = on
    'circuit3_thermostat_signal':   ('informationParams', '116'), # 0 = heat, 1 = no heat
    'circuit3_work_mode':           ('data', '336'),
    'circuit3_day_setpoint':        ('data', '338'),
    'circuit3_night_setpoint':      ('data', '339'),
    'circuit3_hysteresis':          ('data', '340'),
    'circuit3_min_flow_temp':       ('data', '371'),
    'circuit3_max_flow_temp':       ('data', '372'),
    'circuit3_fixed_flow_temp':     ('data', '361'),              # only with fixed regulation
    'circuit3_room_temp':           ('curr', 'Circuit3thermostatTemp'),
}

# Non-numeric values the bridge uses for on/off states. Anything else that can't be converted to a
# number (e.g. '---' for a missing sensor) is treated as unavailable.
STATE_VALUES = {'off': 0, 'on': 1}

# Value reported in regParams 'curr' for sensors which aren't fitted
NO_SENSOR = 999.0

def to_number(value):
    """Convert a value from the bridge to a number, or None if it isn't one. The bridge returns
    numbers, numeric strings, 'on'/'off' for states and placeholders such as '---' for missing
    sensors. Booleans from the JSON are passed through as 0/1 by float().
    """
    if isinstance(value, str):
        value = STATE_VALUES.get(value.strip().lower(), value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def extract_values(regParams, editParams, params_map):
    """Look up each parameter of `params_map` in the regParams and editParams JSON, returning
    ({name: number}, {name: reason}) for the values found and those missing or unusable.
    """
    data = {}
    missing = {}

    # Handle missing fields gracefully so one missing metric won't stop the whole poll.
    for (name, (location, key) ) in params_map.items():
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
        except Exception as e:
            missing[name] = f"{e.__class__.__name__} {e}"
            continue

        number = to_number(value)
        if number is None:
            missing[name] = f"non-numeric value {value!r}"
        elif location == 'curr' and number == NO_SENSOR:
            missing[name] = "sensor not fitted"
        else:
            data[name] = number

    return data, missing

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

        # Names of parameters we've already warned are missing
        self._warned_missing = set()

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

        data, missing = extract_values(regParams, editParams, self._params_map)

        # Which parameters exist depends on how the heat pump is configured, so only warn the first
        # time each one is missing rather than on every poll.
        for name, reason in missing.items():
            if name not in self._warned_missing:
                self._log.warning(f"Unable to retrieve {name}: {reason} (not repeated)")
                self._warned_missing.add(name)
        if missing:
            self._log.debug(f"Skipped {len(missing)} missing values")
        for name in self._warned_missing & data.keys():
            self._log.info(f"{name} is now available")
            self._warned_missing.discard(name)

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
