import time
import json
import Cargo
import requests
from emonhub_interfacer import EmonHubInterfacer

"""
[[Solax]]
    Type = EmonHubSolaxHybridxInterfacer
    [[[init_settings]]]
        ip = 192.168.1.61
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = solax
"""

"""class EmonHubSolaxHybridxInterfacer

Solax interfacer

"""

class EmonHubSolaxHybridxInterfacer(EmonHubInterfacer):

    def __init__(self, name, ip=''):
        """Initialize Interfacer

        """
        # Initialization
        super(EmonHubSolaxHybridxInterfacer, self).__init__(name)

        # This line will stop the default values printing to logfile at start-up
        # self._settings.update(self._defaults)

        # Interfacer specific settings
        self._Solax_settings = {
            'ip': ip,
            'read_interval': 10.0,
            'nodename':'solax'
        }
        
        self.next_interval = True

    def read_from_solax(self, ip):
        # Set IP address of Solax inverter here
        url = 'http://'+ip+':80/api/realTimeData.htm'

        try:
            response = requests.get(url)
        except requests.exceptions.RequestException as ex:
            return None

        try: 
            raw_json = response.text.replace(",,", ",0.0,").replace(",,", ",0.0,")
        except:
            return None

        try:
            data = json.loads(raw_json)
        except ValueError as ex:
            return None

        # Solax HybridX response decoder
        # thanks to:
        # https://github.com/squishykid/solax/blob/master/solax/inverters/x_hybrid.py

        decoder = {
            "PV1 Current": (0, 'A'),
            "PV2 Current": (1, 'A'),
            "PV1 Voltage": (2, 'V'),
            "PV2 Voltage": (3, 'V'),
            "Output Current": (4, 'A'),
            "Network Voltage": (5, 'V'),
            "Power Now": (6, 'W'),
            "Inverter Temperature": (7, 'C'),
            "Today's Energy": (8, 'kWh'),
            "Total Energy": (9, 'kWh'),
            "Exported Power": (10, 'W'),
            "PV1 Power": (11, 'W'),
            "PV2 Power": (12, 'W'),
            "Battery Voltage": (13, 'V'),
            "Battery Current": (14, 'A'),
            "Battery Power": (15, 'W'),
            "Battery Temperature": (16, 'C'),
            "Battery Remaining Capacity": (17, '%'),
            "Month's Energy": (19, 'kWh'),
            "Grid Exported Energy": (41, 'kWh'),
            "Grid Imported Energy": (42, 'kWh'),
            "Grid Frequency": (50, 'Hz'),
            "EPS Voltage": (53, 'V'),
            "EPS Current": (54, 'A'),
            "EPS Power": (55, 'W'),
            "EPS Frequency": (56, 'Hz')
        }

        output = {}
        for key, value in decoder.items():
            output[key] = data['Data'][value[0]]

        return output

    def read(self):
        """Read data and process

        Return data as a list: [NodeID, val1, val2]

        """
        
        if int(time.time())%self._settings['read_interval']==0:
            if self.next_interval: 
                self.next_interval = False

                c = Cargo.new_cargo()
                c.names = []
                c.realdata = []
                c.nodeid = self._settings['nodename']

                data = self.read_from_solax(self._settings['ip'])

                if data:
                    for key, value in data.items():
                        c.names.append(key)
                        c.realdata.append(value)
                    return c

        else:
            self.next_interval = True

        return False


    def set(self, **kwargs):
        for key, setting in self._Solax_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._Solax_settings[key]

            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'read_interval':
                self._log.info("Setting %s read_interval: %s", self.name, setting)
                self._settings[key] = float(setting)
                continue
            elif key == 'nodename':
                self._log.info("Setting %s nodename: %s", self.name, setting)
                self._settings[key] = str(setting)
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)
