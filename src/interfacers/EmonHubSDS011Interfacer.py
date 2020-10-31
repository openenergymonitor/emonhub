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
        
        self.logcols = ["timestamp","pm2.5","pm10","devid"]
        self.readinterval = readinterval
        self.pm_25 = 0
        self.pm_10 = 0
        self.devid = 0
        self.count = 0

        # init the serial port
        self._log.info("Opening SDS011 serial port: " + str(com_port) + " @ "+ str(9600) + " bits/s")
        self.sds = SDS011(port=com_port)
        self._log.info(self.sds)
        self._log.info(self.logcols)
        self.sds.set_working_period(self.readinterval) # one measurment every x minutes offers decent granularity and at least a few years of lifetime to the sensor

        if self.sds is not None:
            self._ser = True
        else:
            self._log.error("Serial port failed to open.")
            self._ser = False

        
       

        # Open serial port
        # self._ser = self._open_serial_port(com_port, 9600, self.readinterval)      
        

    # def close(self):
    #     """Close serial port"""
        
    #     # Close serial port
    #     if self._ser is not None:

    # def _open_serial_port(self, com_port, baudrate, readinterval):
    #     """Open serial port"""
        
        
    #     return s

    def read(self):
        """Read data and process"""

        if not self._ser: return False
        
        meas = self.sds.read_measurement()
        vals = [str(meas.get(k)) for k in self.logcols]

        # Valid packet header
        if vals is not None:
        
            self.pm_25 = vals[1]
            self.pm_10 = vals[2]
            self.devid = vals[3]
            self.count += 1

            self._log.debug("PM2.5 : "+str(self.pm_25)+"μg/m³     PM10 : "+str(self.pm_10)+"μg/m³")

            # create a new cargo object, set data values
            c = Cargo.new_cargo()
            c.nodeid = self._settings['nodename']
            c.names = ["pm_2.5","pm_10","msg","devID"]
            c.realdata = [self.pm_25,self.pm_10,self.count,self.devid]
            return c            
            
        # nothing to return
        return False

    def set(self, **kwargs):
        """

        """

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
                self.sds.set_working_period(int(setting))
                # self._log.info(self.sds)
                continue
            elif key == 'nodename':
                self._log.info("Setting " + self.name + " nodename: " + str(setting))
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super(EmonHubSDS011Interfacer, self).set(**kwargs)

