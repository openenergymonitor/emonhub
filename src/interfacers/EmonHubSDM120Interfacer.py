import time
import json
import Cargo
import os
import glob
from emonhub_interfacer import EmonHubInterfacer

"""
[[SDM120]]
    Type = EmonHubSDM120Interfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sdm120
"""

"""class EmonHubSDM120Interfacer

SDM120 interfacer for use in development

"""

class EmonHubSDM120Interfacer(EmonHubInterfacer):

    def __init__(self, name, device="/dev/modbus", baud=2400):
        """Initialize Interfacer

        """
        # Initialization
        super(EmonHubSDM120Interfacer, self).__init__(name)

        # This line will stop the default values printing to logfile at start-up
        # self._settings.update(self._defaults)

        # Interfacer specific settings
        self._SDM120_settings = {'read_interval': 10.0,'nodename':'sdm120'}
        
        self.next_interval = True
        
        # Only load module if it is installed        
        try: 
            import sdm_modbus
            self._log.info("Connecting to SDM120 device="+str(device)+" baud="+str(baud))
            self._sdm = sdm_modbus.SDM120(device="/dev/modbus", baud=2400)
            self._sdm_registers = sdm_modbus.registerType.INPUT
        except ModuleNotFoundError as err:
            self._log.error(err)
            self._sdm = False
                    

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
             
                if self._sdm and self._sdm.connected():
                    r = self._sdm.read_all(self._sdm_registers)
                    
                    # for i in r:
                    #     self._log.debug(i+" "+str(r[i]))
                    
                    self._log.debug("%.2f %.2f %.4f %.4f %.3f %.3f" % (r['voltage'],r['power_active'],r['power_factor'],r['frequency'],r['import_energy_active'],r['current']))
                    
                    c.names = ['sdm_V','sdm_P','sdm_PF','sdm_FR','sdm_E','sdm_I']
                    c.realdata = [
                      round(r['voltage'],2),
                      round(r['power_active'],2),
                      round(r['power_factor'],4),
                      round(r['frequency'],4),
                      round(r['import_energy_active'],3),
                      round(r['current'],3)
                    ]
                    
                    if len(c.realdata)>0:
                        return c
                else:
                     self._log.error("Could not read from SDM120")
                    
        else:
            self.next_interval = True
            
        return False


    def set(self, **kwargs):
        for key, setting in self._SDM120_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._SDM120_settings[key]
                
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
