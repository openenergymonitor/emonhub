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
        # Include comma even if only one pin
        pins = 13, 15
        invert = 1
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        nodename = gpio
        read_interval = 10
"""

class EmonHubDigitalInputInterfacer(EmonHubInterfacer):

    def __init__(self, name, pins, invert=0):
        """Initialize interfacer

        """

        # Initialization
        super().__init__(name)

        # if pins is a string, convert to list
        if isinstance(pins, str):
            pins = pins.split(',')
            # convert to int
            pins = [int(p) for p in pins]

        self._settings.update({
            'pins'  : pins,
            'invert' : int(invert),
            'read_interval' : 10,
            'nodename' : 'gpio'
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

        for pin in self._settings['pins']:
            self._log.info('%s : Setting up digital pin: %d', self.name, pin)
            GPIO.setup(int(pin), GPIO.IN)

    def read(self):

        if int(time.time()) % self._settings['read_interval'] == 0:

            # Read the digital pin state
            # state = GPIO.input(self._settings['digital_pin'])
            # self._log.debug('%s : state: %d', self.name, state)

            # Add to cargo
            time_now = int(time.time())
            c = Cargo.new_cargo(nodename=self.name, timestamp=time_now)

            for pin in self._settings['pins']:
                state = GPIO.input(int(pin))
                self._log.debug('%s : state: %d', self.name, state)

                # Invert the state if invert is set
                if self._settings['invert']:
                    state = not state

                c.realdata.append(state)
                c.names.append("pin" + str(pin))

            c.nodeid = self._settings['nodename']

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

            # How fast to read the digital pins
            elif key == 'read_interval':
                self._log.info("Setting %s read_interval: %s", self.name, setting)
                self._settings[key] = float(setting)
                # Minimum read interval is 1 second
                if self._settings[key] < 1:
                    self._settings[key] = 1
                continue

            # Option to set nodename
            elif key == 'nodename':
                self._log.info("Setting %s nodename: %s", self.name, setting)
                self._settings[key] = str(setting)
                continue

            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
