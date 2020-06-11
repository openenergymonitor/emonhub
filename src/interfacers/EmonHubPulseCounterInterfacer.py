from emonhub_interfacer import EmonHubInterfacer
from collections import defaultdict
import time
import atexit
import RPi.GPIO as GPIO

import Cargo

"""class EmonhubPulseCounterInterfacer

Monitors GPIO pins for pulses

"""

class EmonHubPulseCounterInterfacer(EmonHubInterfacer):

    def __init__(self, name, pulse_pins=None, bouncetime=1):
        """Initialize interfacer

        """

        # Initialization
        super().__init__(name)

        self._settings.update( {
            'pulse_pins': pulse_pins,
            'bouncetime' : bouncetime,
        })

        self.gpio_pin = int(pulse_pins)

        self._pulse_settings = {}

#        self._settings.update(self._pulse_settings)

        self.pulse_count = defaultdict(int)

        self.pulse_received = 0

        self.init_gpio()

    def init_gpio(self):
        """Register GPIO callbacks

        """

        atexit.register(GPIO.cleanup)
        GPIO.setmode(GPIO.BOARD)
        self._log.debug('Pulse pin set to: %d', self.gpio_pin)
        GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(self.gpio_pin, GPIO.FALLING, callback=self.process_pulse, bouncetime=int(self._settings['bouncetime']))

    def process_pulse(self, channel):
        self.pulse_count[channel] += 1
        self._log.debug('Pulse Channel %d pulse: %d', channel, self.pulse_count[channel])
        self.pulse_received += 1

    def read(self):

        if self.pulse_received == 0:
            return False

        self.pulse_received = 0

        # Create a Payload object
        c = Cargo.new_cargo()
        c.names = ["Pulse"]
        c.realdata = [self.pulse_count[self.gpio_pin]]

        if int(self._settings['nodeoffset']):
            c.nodeid = int(self._settings['nodeoffset'])
        else:
            c.nodeid = 0
        return c


    def set(self, **kwargs):
        super().set(**kwargs)

        for key, setting in self._pulse_settings.items():

            if key not in kwargs:
#                self._log.error("ERROR 1 %s", key)
                setting = self._pulse_settings[key]
            else:
#                self._log.error("ERROR 2")
                setting = kwargs[key]

            if key in self._settings and self._settings[key] == setting:
#                self._log.error("ERROR 3 %s", key)
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
