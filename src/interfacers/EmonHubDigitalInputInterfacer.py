from emonhub_interfacer import EmonHubInterfacer
import time
import atexit

import Cargo

try:
    import RPi.GPIO as GPIO
    RPi_found = True
except:
    RPi_found = False

"""class EmonHubDigitalInputInterfacer

Authors @trystanlea based on pulse counter interfacer by @borpin & @bwduncan
Version: 1
Date: 02 September 2024

Monitors GPIO pins for digital  state

Example emonhub configuration
[[digital]]
    Type = EmonHubDigitalInputInterfacer
    [[[init_settings]]]
        # pin number must be specified. Create a second
        # interfacer for more than one digital pin
        digital_pin = 15
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,

        # Default NodeID is 0. Use nodeoffset to set NodeID
        # No decoder required as key:value pair returned
        nodeoffset = 3
        read_interval = 10
"""

class EmonHubDigitalInputInterfacer(EmonHubInterfacer):

    def __init__(self, name, digital_pin=None, read_interval=10):
        """Initialize interfacer

        """

        # Initialization
        super().__init__(name)

        self._settings.update({
            'digital_pin'  : int(digital_pin),
            'read_interval' : int(read_interval)
        })

        self._digital_settings = {}

        if RPi_found:
            self.init_gpio()
        else:
            self._log.error("Pulse counter not initialised. Please install the RPi GPIO Python3 module")

    def init_gpio(self):
        """Register GPIO callbacks

        """

        atexit.register(GPIO.cleanup)
        GPIO.setmode(GPIO.BOARD)
        self._log.info('%s : Digital pin set to: %d', self.name, self._settings['digital_pin'])
        GPIO.setup(self._settings['digital_pin'], GPIO.IN)

    def read(self):

        if int(time.time()) % self._settings['read_interval'] == 0:

            # Read the digital pin state
            state = GPIO.input(self._settings['digital_pin'])
            self._log.debug('%s : state: %d', self.name, state)

            # Add to cargo
            c = Cargo.new_cargo(nodename=self.name, timestamp=time_now)
            c.names = ["digital"]
            c.realdata = [state]

            if int(self._settings['nodeoffset']):
                c.nodeid = int(self._settings['nodeoffset'])
            else:
                c.nodeid = 0

            # Minimum sleep time is 1 second
            time.sleep(1)

            return c


    def set(self, **kwargs):
        super().set(**kwargs)

        for key, setting in self._digital_settings.items():

            if key not in kwargs:
                setting = self._digital_settings[key]
            else:
                setting = kwargs[key]

            if key in self._settings and self._settings[key] == setting:
                continue

            elif key == 'read_interval':
                self._log.info("Setting %s read_interval: %s", self.name, setting)
                self._settings[key] = float(setting)
                continue

            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
