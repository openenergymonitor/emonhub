import time
import json
import Cargo
import requests
import emonhub_coder

from emonhub_interfacer import EmonHubInterfacer

"""class EmonFroniusAPIInterfacer

Template interfacer for use in development

"""

class EmonHubFroniusAPIInterfacer(EmonHubInterfacer):

    def __init__(self, name,  webAPI_IP='192.168.1.13', webAPI_port=0):
        """Initialize Interfacer

        """

        # Initialization
        super().__init__(name)

        # add or alter any default settings for this interfacer
        # defaults previously defined in inherited emonhub_interfacer
        # here we are just changing the batchsize from 1 to 100
        # and the interval from 0 to 30
        # self._defaults.update({'batchsize': 100,'interval': 30})

        # This line will stop the default values printing to logfile at start-up
        #self._settings.update(self._defaults)

        # Interfacer specific settings
        # (settings not included in the inherited EmonHubInterfacer)
        # The set method below is called from emonhub.py on
        # initialisation and settings change and copies the
        # interfacer specific settings over to _settings
        #self._template_settings = {'read_interval': 10.0}
       # self._template_settings = {'webAPI_IP': '192.168.1.13'}
       # #self._template_settings = ('webAPI_port': 69}
       # try:
       #     webAPI_IP =  self.init_settings['webAPI_IP']
       #     webAPI_port =  self.init_settings['webAPI_port']
       # except Exception as err:
       #     print("Other error occurred: " + str(err))
        self.webAPI_IP = webAPI_IP
        self.webAPI_port = webAPI_port
        self._log.debug("EmonModbusTcpInterfacer args: %s - %s", webAPI_IP, webAPI_port)
        #print(self.webAPI_IP)
        #print(self.webAPI_port)


    def read(self):
        """Read data and process

        Return data as a list: [NodeID, val1, val2]

        """
        self._log.info("starting read")
        self._log.debug("EmonHubAPIInterfacer args: %s - %s", self.webAPI_IP, self.webAPI_port)

        # create a new cargo object, set data values
        time.sleep(float(self._settings['interval']))
        f = []
        c = Cargo.new_cargo(rawdata="")

      #get inverter status
        url = "http://" +self.init_settings["webAPI_IP"] + "/solar_api/v1/GetInverterInfo.cgi"
        try:
            self._log.debug("Status URL: " + url)
            response = requests.get(url)
            response.raise_for_status()
        except HTTPError as http_err:
            self._log.error("HTTP error occurred: "+ str(http_err))
        except Exception as err:
            self._log.error("Other error occurred: " + str(err))
        else:

            response_dict = response.json()
            Inverter_status=response_dict["Body"]["Data"]["1"]["StatusCode"]
            self._log.info("webAPI inverter status: " + str(Inverter_status))
            self._log.debug("Inverter Status Code " + str(Inverter_status))
            self._log.info("webAPI Device Offline")

            t = emonhub_coder.encode('H',Inverter_status)
            f = f + list(t)

          # get local grid power data
            
            url = "http://"+self.init_settings["webAPI_IP"]+"/solar_api/v1/GetPowerFlowRealtimeData.fcgi"
            try:
                self._log.debug("Status URL: " + url)
                response = requests.get(url)
                response.raise_for_status()
            except HTTPError as http_err:
                self._log.error("HTTP error occurred: "+ str(http_err))
            except Exception as err:
                self._log.error("Other error occurred: " + st(err))
            else:
                 response_dict = response.json()
                 AC_power_watts = response_dict["Body"]["Data"]["Inverters"]["1"]["P"]
                 t = emonhub_coder.encode('f',AC_power_watts * 10)
                 f = f + list(t)
                 AC_LifetimekWh = response_dict["Body"]["Data"]["Inverters"]["1"]["E_Total"]
                 t = emonhub_coder.encode('f',AC_LifetimekWh * 10)
                 f = f + list(t)
                 DayWh = response_dict["Body"]["Data"]["Inverters"]["1"]["E_Day"]
                 t = emonhub_coder.encode('f',DayWh * 1)
                 f = f + list(t)

            # send dummy results for invertstring data as its not available in the api
            for x in range(4):
                t = emonhub_coder.encode('h',0)
                f = f + list(t)

            PhVphA = 0
            PhVphB = 0
            PhVphC = 0

            if Inverter_status == 7 : # 7 = Inverter running
                
              # get inverter 3phase data phase amps and phase voltage
                url = "http://"+self.init_settings["webAPI_IP"]+"/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&DeviceID=1&DataCollection=3PInverterData&DeviceId=1"
                try:
                    self._log.debug("Status URL: " + url)
                    response = requests.get(url)
                    response.raise_for_status()
                except HTTPError as http_err:
                    self._log.error("HTTP error occurred: "+ str(http_err))
                except Exception as err:
                    self._log.error("Other error occurred: " + st(err))
                else:
                    response_dict = response.json()
                    PhVphA = response_dict["Body"]["Data"]["UAC_L1"]["Value"]
                    PhVphB = response_dict["Body"]["Data"]["UAC_L2"]["Value"]
                    PhVphC = response_dict["Body"]["Data"]["UAC_L3"]["Value"]
            t = emonhub_coder.encode('f',PhVphA * 10)
            f = f + list(t)
            t = emonhub_coder.encode('f',PhVphB * 10)
            f = f + list(t)
            t = emonhub_coder.encode('f',PhVphC * 10)
            f = f + list(t)


            self._log.debug("reporting data: " + str(f))
            if int(self._settings['nodeId']):
                c.nodeid = int(self._settings['nodeId'])
                c.realdata = f
            else:
                c.nodeid = int(12)
                c.realdata = f
            self._log.debug("Return from read data: " + str(c.realdata))
        return c


    def set(self, **kwargs):
        for key in kwargs:
            setting = kwargs[key]
            self._settings[key] = setting
            self._log.debug("Setting %s %s: %s", self.name, key, setting)
