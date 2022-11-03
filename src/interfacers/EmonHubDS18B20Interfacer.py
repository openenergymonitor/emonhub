import time
import json
import Cargo
import os
import glob
from emonhub_interfacer import EmonHubInterfacer

"""
[[DS18B20]]
    Type = EmonHubDS18B20Interfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        ids = 28-000008e2db06, 28-000009770529, 28-0000096a49b4
        names = ambient, cylb, cylt
"""

class DS18B20:
    def __init__(self):
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')
        self._base_dir = '/sys/bus/w1/devices/'

    def scan(self):
        devices = glob.glob(self._base_dir + '28*')
        sensors = []
        for device in devices:
            sensor = device.replace(self._base_dir, "")
            sensors.append(sensor)
        return sensors

    def _read_raw(self, sensor):
        f = open(self._base_dir + sensor + '/w1_slave', 'r')
        lines = f.readlines()
        f.close()
        return lines

    def tempC(self, sensor):
        lines = self._read_raw(sensor)
        # retry = 0
        if len(lines[0]):
            while lines[0].strip()[-3:] != 'YES':
                # time.sleep(0.2)
                # lines = self._read_raw(sensor)
                # retry += 1
                # if retry==3: return False
                return False

        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            return temp_c

"""class EmonHubDS18B20Interfacer

DS18B20 interfacer for use in development

"""

class EmonHubDS18B20Interfacer(EmonHubInterfacer):

    def __init__(self, name):
        """Initialize Interfacer

        """
        # Initialization
        super(EmonHubDS18B20Interfacer, self).__init__(name)

        # This line will stop the default values printing to logfile at start-up
        # self._settings.update(self._defaults)

        # Interfacer specific settings
        self._DS18B20_settings = {'read_interval': 10.0, 'nodename':'sensors', 'ids':[], 'names':[]}

        self.ds = DS18B20()

        self.next_interval = True


    def read(self):
        """Read data and process

        Return data as a list: [NodeID, val1, val2]

        """

        if int(time.time()) % self._settings['read_interval'] == 0:
            if self.next_interval:
                self.next_interval = False

                c = Cargo.new_cargo()
                c.names = []
                c.realdata = []
                c.nodeid = self._settings['nodename']

                if self.ds:
                    for sensor in self.ds.scan():
                        # Check if user has set a name for given sensor id
                        name = sensor
                        try:
                            index = self._settings['ids'].index(sensor)
                            if index < len(self._settings['names']):
                                name = self._settings['names'][index]
                        except ValueError:
                            pass

                        # Read sensor value
                        value = self.ds.tempC(sensor)

                        # Add sensor to arrays
                        c.names.append(name)
                        c.realdata.append(value)

                        # Log output
                        self._log.debug(sensor + ": " + name + " " + str(value))

                    if len(c.realdata) > 0:
                        return c

        else:
            self.next_interval = True

        return False


    def set(self, **kwargs):
        for key, setting in self._DS18B20_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._DS18B20_settings[key]

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
            elif key == 'ids':
                self._log.info("Setting %s ids: %s", self.name, ", ".join(setting))
                self._settings[key] = setting
                continue
            elif key == 'names':
                self._log.info("Setting %s names: %s", self.name, ", ".join(setting))
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)
