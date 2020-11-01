# -*- coding: UTF-8 -*-

import time, Cargo, serial, struct
from sds011 import SDS011
from emonhub_interfacer import EmonHubInterfacer

"""
class EmonHubSDS011Interfacer

$ sudo pip3 install sds011
https://pypi.org/project/sds011/

[interfacers]
### This interfacer sets up and manages the SDS011 dust sensor.
[[SDS011]]
     Type = EmonHubSDS011Interfacer
      [[[init_settings]]]
           # default com port if using USB to UART adapter
           com_port = /dev/ttyUSB0
      [[[runtimesettings]]]
           # one measurment every few minutes offers decent granularity and at least a few years of lifetime to the sensor
           # a value of 0 for a reading every second.
           readinterval = 5
           nodename = SDS011
           pubchannels = ToEmonCMS,

"""

class EmonHubSDS011Interfacer(EmonHubInterfacer):

    def __init__(self, name, com_port="", readinterval=5):
        """Initialize Interfacer"""
        # Initialization
        super(EmonHubSDS011Interfacer, self).__init__(name)

        self._settings.update(self._defaults)

        self._template_settings = {'nodename':'SDS011','readinterval':5}
        
        ### GLOBALS ###
        self.previous_time = time.time()
        self.warmup_time = 15 # seconds to spin up the SDS011 before taking a reading
        self.sensor_present = False
        self.first_reading_done = False
        self.sensor_waking = False
        self.timenow = time.time()
        self.count = 0

        self.readinterval = readinterval * 60 # convert to seconds.
        ### INIT COM PORT ###
        try:
            print("INFO: Opening sensor serial port...")
            self.sensor = SDS011(com_port, use_query_mode=False)
            # self.sensor.set_work_period
            self.sensor.sleep(sleep=False) # wake the sensor just in case.
            time.sleep(1)
            first_reading = self.sensor.query()
            # sensor.set_report_mode
            self.previous_time = time.time()
            if first_reading is not None:
                self._log.info("COM port open and SDS011 active")
                self._log.info("testing reading PM2.5/PM10: " + str(first_reading))
                self.sensor_present = True
            else:
                self._log.error("COM port opened but sensor readings unavailable.")
                self._log.info("Check connections or the selected COM port in settings")
        except:
            self._log.error("Couldn't open COM port")

    def close(self):
        self._log.error("no closing script")

    def read(self):
        """Read data and process"""

        if not self.sensor_present: return False
        
        self.timenow = time.time()
        
        # readings = [0.0,0.0]

        if self.first_reading_done is False:
            if self.timenow >= (self.previous_time + self.warmup_time): # 15 seconds warmup for first reading, just in case.
                self.previous_time = self.timenow
                readings = self.sensor.query()
                readings = list(readings)
                self._log.debug("First readings:" + str(readings))
                if self.readinterval:
                    self.sensor.sleep()
                    self._log.debug("Sensor put to sleep")
                self.first_reading_done = True
                self.count += 1
                # create a new cargo object, set data values
                c = Cargo.new_cargo()
                c.nodeid = self._settings['nodename']
                c.names = ["pm_2.5","pm_10","msg"]
                c.realdata = [readings[0],readings[1],self.count]
                return c 

        if self.timenow >= (self.previous_time + self.readinterval):
            self.previous_time = self.timenow
            readings = self.sensor.query()
            readings = list(readings)
            self._log.debug("Readings:" + str(readings))
            if self.readinterval:
                self.sensor.sleep()
                self._log.debug("Sensor returned to sleep")
            self.sensor_waking=False
            self.count += 1
            # create a new cargo object, set data values
            c = Cargo.new_cargo()
            c.nodeid = self._settings['nodename']
            c.names = ["pm_2.5","pm_10","msg"]
            c.realdata = [readings[0],readings[1],self.count]
            return c 
        elif self.timenow >= (self.previous_time + self.readinterval - self.warmup_time):
            if self.sensor_waking:
                return False    
            self.sensor.sleep(sleep=False)
            self._log.debug("Sensor warming up... 15s until reading")
            self.sensor_waking=True
            return False
    

        # nothing to return
        return False
        

    def set(self, **kwargs):
        """ Runtime Settings """

        for key, setting in self._template_settings.items():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._template_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'readinterval':
                self._log.info("Setting " + self.name + " readinterval: " + str(setting))
                self._settings[key] = int(setting)
                self.readinterval = int(setting) * 60
                continue
            elif key == 'nodename':
                self._log.info("Setting " + self.name + " nodename: " + str(setting))
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super(EmonHubSDS011Interfacer, self).set(**kwargs)

