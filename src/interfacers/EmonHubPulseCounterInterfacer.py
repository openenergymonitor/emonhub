from emonhub_interfacer import EmonHubInterfacer
from collections import defaultdict
import time
import atexit
import RPi.GPIO as GPIO

import Cargo

"""class EmonhubPulseCounterInterfacer

Authors @borpin & @bwduncan
Version: 1
Date: 11 June 2020

Monitors GPIO pins for pulses

Example emonhub configuration
[[pulse2]]
    Type = EmonHubPulseCounterInterfacer
    [[[init_settings]]]
        # pin number must be specified. Create a second 
        # interfacer for more than one pulse sensor
        pulse_pin = 15
        # bouncetime default to 1.
        # bouncetime = 2
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,

        # Default NodeID is 0. Use nodeoffset to set NodeID
        # No decoder required as key:value pair returned
        nodeoffset = 3
"""

class EmonHubPulseCounterInterfacer(EmonHubInterfacer):

    def __init__(self, name, pulse_pin=None, bouncetime=1):
        """Initialize interfacer

        """

        # Initialization
        super().__init__(name)

        self._settings.update( {
            'pulse_pin': int(pulse_pin),
            'bouncetime' : bouncetime,
        })

        self._pulse_settings = {}

        self.pulse_count = defaultdict(int)

        self.pulse_received = False

        self.init_gpio()

    def init_gpio(self):
        """Register GPIO callbacks

        """

        atexit.register(GPIO.cleanup)
        GPIO.setmode(GPIO.BOARD)
        self._log.info('%s : Pulse pin set to: %d', self.name, self._settings['pulse_pin'])
        GPIO.setup(self._settings['pulse_pin'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(self._settings['pulse_pin'], GPIO.FALLING, callback=self.process_pulse, bouncetime=int(self._settings['bouncetime']))

    def process_pulse(self, channel):
        self.pulse_count[channel] += 1
        self._log.debug('%s : Pulse Channel %d pulse: %d', self.name, channel, self.pulse_count[channel])
        self.pulse_received = True

    def read(self):

        if not self.pulse_received:
            return False

        self.pulse_received = False

        # Create a Payload object
        c = Cargo.new_cargo(nodename=self.name)
        c.names = ["PulseCount"]
        c.realdata = [self.pulse_count[self._settings['pulse_pin']]]

        if int(self._settings['nodeoffset']):
            c.nodeid = int(self._settings['nodeoffset'])
        else:
            c.nodeid = 0
        return c


    def set(self, **kwargs):
        super().set(**kwargs)

        for key, setting in self._pulse_settings.items():

            if key not in kwargs:
                setting = self._pulse_settings[key]
            else:
                setting = kwargs[key]

            if key in self._settings and self._settings[key] == setting:
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
