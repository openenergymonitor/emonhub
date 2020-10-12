# -*- coding: UTF-8 -*-

import time, Cargo, serial, struct
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubTemplateInterfacer

Template interfacer for use in development

"""

class EmonHubSDS011Interfacer(EmonHubInterfacer):

    def __init__(self, name, serial_port='/dev/ttyUSB0'):
        """Initialize Interfacer
        
        """
        # Initialization
        super(EmonHubSDS011Interfacer, self).__init__(name)

        self._settings.update(self._defaults)

        self._template_settings = {'nodename':'SDS011','readinterval':10.0}

        # Open serial port
        self._ser = self._open_serial_port(serial_port, 9600)

        self.byte, self.lastbyte = "\x00", "\x00"
        self.pm_25_sum = 0
        self.pm_10_sum = 0
        self.count = 0
        self.lasttime = time.time()

    def close(self):
        """Close serial port"""
        
        # Close serial port
        if self._ser is not None:
            self._log.debug("Closing serial port")
            self._ser.close()

    def _open_serial_port(self, serial_port, baudrate):
        """Open serial port"""
        
        try:
            s = serial.Serial(serial_port, baudrate, stopbits=1, parity="N", timeout=2)
            s.flushInput()
            self._log.debug("Opening serial port: " + str(serial_port) + " @ "+ str(baudrate) + " bits/s")
        except serial.SerialException as e:
            self._log.error(e)
            s = False
        return s

    def read(self):
        """Read data and process
        
        """
        if not self._ser: return False
        
        self.lastbyte = self.byte
        self.byte = self._ser.read(size=1)
        
        # Valid packet header
        if self.lastbyte == b"\xaa" and self.byte == b"\xc0":
        
            sentence = self._ser.read(size=8) # Read 8 more bytes
            readings = struct.unpack('<hhxxcc',sentence) # Decode the packet - big endian, 2 shorts for pm2.5 and pm10, 2 reserved bytes, checksum, message tail
            
            pm_25 = readings[0]/10.0
            pm_10 = readings[1]/10.0
            
            # self._log.debug("PM 2.5:"+str(pm_25)+"μg/m^3  PM 10:"+str(pm_10)+"μg/m^3")

            self.pm_25_sum += pm_25
            self.pm_10_sum += pm_10
            self.count = self.count + 1

        # Average over 10 seconds
        if (time.time()-self.lasttime)>=self._settings['readinterval']:
            self.lasttime = time.time()
            if self.count>0:
                pm_25 = round(self.pm_25_sum/self.count,3)
                pm_10 = round(self.pm_10_sum/self.count,3)
                self.pm_25_sum = 0
                self.pm_10_sum = 0
                self.count = 0
                self._log.debug("PM 2.5:"+str(pm_25)+"μg/m^3  PM 10:"+str(pm_10)+"μg/m^3")

                # create a new cargo object, set data values
                c = Cargo.new_cargo()
                c.nodeid = self._settings['nodename']
                c.names = ["pm_25","pm_10"]
                c.realdata = [pm_25,pm_10]
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
                self._settings[key] = float(setting)
                continue
            elif key == 'nodename':
                self._log.info("Setting " + self.name + " nodename: " + str(setting))
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super(EmonHubSDS011Interfacer, self).set(**kwargs)

