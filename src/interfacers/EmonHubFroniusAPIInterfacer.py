import time
import requests
import Cargo
from emonhub_interfacer import EmonHubInterfacer

"""
[[Fronius]]
    Type = EmonHubFroniusAPIInterfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        name = fronius
        host = 192.168.1.11
        readinterval = 10
"""

"""class EmonHubFroniusAPIInterfacer

Reads a Fronius inverter, and the smart meter connected to it, over the
Fronius Solar API (http://<host>/solar_api/v1/).

Every readinterval seconds it requests:
- GetPowerFlowRealtimeData: PV, grid, load and battery power and the energy totals
- GetInverterInfo: the inverter status code
- GetInverterRealtimeData (3PInverterData): phase voltages and currents,
  only while the inverter is running

Values are published by name, so a value the system does not report (no battery,
no meter, a single phase inverter, an inverter asleep at night) is left out
without affecting the others. If the power flow request fails nothing is published.
"""

# Inverter status code while feeding in
STATUS_RUNNING = 7

# Input name, key in Body.Data.Site of GetPowerFlowRealtimeData
SITE_VALUES = (
    ("pv_power", "P_PV"),
    ("grid_power", "P_Grid"),
    ("load_power", "P_Load"),
    ("battery_power", "P_Akku"),
    ("day_energy", "E_Day"),
    ("total_energy", "E_Total"),
)

# Input name, key in Body.Data of GetInverterRealtimeData 3PInverterData
PHASE_VALUES = (
    ("voltage_l1", "UAC_L1"),
    ("voltage_l2", "UAC_L2"),
    ("voltage_l3", "UAC_L3"),
    ("current_l1", "IAC_L1"),
    ("current_l2", "IAC_L2"),
    ("current_l3", "IAC_L3"),
)

# Errors from an unreachable inverter or an unexpected reply
REQUEST_ERRORS = (requests.exceptions.RequestException, ValueError, KeyError, TypeError)


class EmonHubFroniusAPIInterfacer(EmonHubInterfacer):

    # seconds to wait for each request
    TIMEOUT = 5

    def __init__(self, name):
        super().__init__(name)

        self._settings.update(self._defaults)

        # Interfacer specific settings
        self._template_settings = {'name': 'fronius',
                                   'host': '',
                                   'device_id': '1',
                                   'readinterval': 10.0}

        self._last_time = 0
        self._failing = False

    def read(self):
        # Request inverter data at user specified interval
        if time.time() - self._last_time < self._settings['readinterval']:
            return
        self._last_time = time.time()

        if not self._settings['host']:
            return

        try:
            values = self._fetch()
        except REQUEST_ERRORS as e:
            # Warn when requests start failing, not on every one
            if not self._failing:
                self._log.warning("%s couldn't read inverter at %s: %s", self.name, self._settings['host'], e)
                self._failing = True
            return

        if self._failing:
            self._log.info("%s inverter at %s reachable again", self.name, self._settings['host'])
            self._failing = False

        c = Cargo.new_cargo()
        c.nodeid = self._settings['name']
        c.names = list(values.keys())
        c.realdata = list(values.values())
        return c

    def _get(self, path):
        """Request a Solar API path and return Body.Data"""
        url = "http://%s/solar_api/v1/%s" % (self._settings['host'], path)
        reply = requests.get(url, timeout=self.TIMEOUT)
        reply.raise_for_status()
        response = reply.json()
        status = response["Head"]["Status"]
        if status["Code"] != 0:
            raise ValueError("%s: error %s %s" % (path, status["Code"], status.get("Reason", "")))
        return response["Body"]["Data"]

    def _fetch(self):
        """Return a dict of input name: value"""
        values = {}

        site = self._get("GetPowerFlowRealtimeData.fcgi")["Site"]
        for name, key in SITE_VALUES:
            value = site.get(key)
            # P_PV is null while the inverter is asleep
            if value is None and key == "P_PV":
                value = 0
            if value is not None:
                values[name] = value

        # Status and phase data are optional, publish the power flow values without them
        device_id = str(self._settings['device_id'])
        try:
            status = self._get("GetInverterInfo.cgi")[device_id]["StatusCode"]
        except REQUEST_ERRORS as e:
            self._log.debug("%s no inverter status: %s", self.name, e)
            return values
        values["inverter_status"] = status

        if status == STATUS_RUNNING:
            path = "GetInverterRealtimeData.cgi?Scope=Device&DeviceId=%s&DataCollection=3PInverterData" % device_id
            try:
                data = self._get(path)
            except REQUEST_ERRORS as e:
                self._log.debug("%s no phase data: %s", self.name, e)
                return values
            for name, key in PHASE_VALUES:
                item = data.get(key)
                if isinstance(item, dict) and item.get("Value") is not None:
                    values[name] = item["Value"]

        return values

    def set(self, **kwargs):
        for key, setting in self._template_settings.items():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            if key == 'readinterval':
                try:
                    setting = float(setting)
                except ValueError:
                    self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
                    continue
            self._log.info("Setting %s %s: %s", self.name, key, setting)
            self._settings[key] = setting

        # include kwargs from parent
        super().set(**kwargs)
