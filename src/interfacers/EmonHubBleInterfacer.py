import time
import struct

try:
    from bluepy import btle
    btle_found = True
except ImportError:
    btle_found = False

import Cargo
from emonhub_interfacer import EmonHubInterfacer

"""class EmonhubBleInterfacer

Polls a Bluetooth LE sensor for temperature, huimidity and battery level

Currently only tested with a Silicon Labs Thunderboard Sense 2


Example config snippets:

[interfacers]

[[blesensor]]
    Type = EmonHubBleInterfacer
    [[[init_settings]]]
        device_addr = '00:0b:57:64:8c:a2'
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 20

[nodes]

[[1]]
    nodename = Sensornode

    [[[rx]]]
        names = temp,humidity,battery
        scales = 0.01,0.01,1
        units = C,%,%

"""

class EmonHubBleInterfacer(EmonHubInterfacer):

    def __init__(self, name, device_addr=''):
        """Initialize interfacer

        device_addr (string): BLE MAC address to connect to

        """

        # Initialization
        super(EmonHubBleInterfacer, self).__init__(name)

        self._private_settings = {
            'read_interval': 60
        }

        self._addr = device_addr
        self._last_read_time = 0
        self._bat_readings = []
        if btle_found:
            self._connect()

    def close(self):
        """Close serial port"""

        # Close serial port
        if self._ble is not None:
            self._log.debug("Closing Bluetooth connection")
            self._ble.disconnect()

        return

    def read(self):
        """Read data from bluetooth sensor

        """
        if not btle_found:
            return False

        # Don't read before the configured interval
        interval = int(self._private_settings['read_interval'])
        if time.time() - self._last_read_time < interval:
            return

        self._last_read_time = time.time()

        # Check connection, connect if we didn't connect during init
        if not self._ble:
            self._connect()

        if not self._ble:
            return False

        temp = self._get_temperature()
        rh = self._get_humidity()
        bat = self._get_bat_level()

        data = '{}, {}, {}'.format(temp, rh, bat )

        # Create a Payload object
        c = Cargo.new_cargo(rawdata=data)
        c.realdata = (temp, rh, bat)

        if int(self._settings['nodeoffset']):
            c.nodeid = int(self._settings['nodeoffset'])
        else:
            c.nodeid = 1

        return c

    def set(self, **kwargs):

        for key, setting in self._private_settings.iteritems():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._private_settings[key]

            # Ignore unchanged
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'read_interval':
                setting = float(setting)
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))
                continue

            self._log.debug('Setting {}: {}'.format(key, setting))
            self._private_settings[key] = setting

        # include kwargs from parent
        super(EmonHubBleInterfacer, self).set(**kwargs)

    def _get_temperature(self):
        val = self._temperature.read()
        (val,) = struct.unpack('h', val)
        return val

    def _get_humidity(self):
        val = self._humidity.read()
        (val,) = struct.unpack('h', val)
        return val

    def _get_bat_level(self):
        val = self._bat_level.read()
        (val,) = struct.unpack('B', val)

        # The battery reading is very noisy - do a simple average
        self._bat_readings.insert(0, val)
        self._bat_readings = self._bat_readings[0:20]

        val = sum(self._bat_readings)/float(len(self._bat_readings))
        #self._log.debug('Batt: {} -> {}'.format(self._bat_readings, val))
        
        return round(val)

    def _connect(self):
        self._log.debug("Connecting to BLE address {}...".format(self._addr))
        self._ble = None

        try:
            self._ble = btle.Peripheral(self._addr)
        except btle.BTLEException as e:
            self._log.error(e)
            return False

        self._temperature = self._ble.getCharacteristics(uuid=btle.AssignedNumbers.temperature)[0]
        self._humidity = self._ble.getCharacteristics(uuid=btle.AssignedNumbers.humidity)[0]
        self._bat_level = self._ble.getCharacteristics(uuid=btle.AssignedNumbers.battery_level)[0]

        return True

