import time
import json
import re
import Cargo
import serial
import struct
import asyncio
import concurrent.futures
import threading

from emonhub_interfacer import EmonHubInterfacer
from xknx import XKNX
from xknx.io import ConnectionConfig, ConnectionType

from xknx.devices import Light
from xknx.devices import NumericValue
from xknx.devices import RawValue
from xknx.devices import Sensor
from xknx.dpt import DPTArray
from xknx.telegram import GroupAddress, Telegram
from xknx.telegram.apci import GroupValueRead, GroupValueResponse, GroupValueWrite
from xknx.core import ValueReader

"""
[[KNX]]
    Type = EmonHubKNXInterfacer
    [[[init_settings]]]
        gateway_ip = 192.168.254.40
        port = 3691
        local_ip = 192.168.254.1
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = KNX
        [[[[meters]]]]
            [[[[[compteur]]]]]
                group=1/1/1
                eis=DPT-14
            [[[[[[consommationWh]]]]]]
                group=10/5/1
                eis=DPT-12
"""

"""class EmonHubKNXInterfacer

KNX interfacer

"""

class EmonHubKNXInterfacer(EmonHubInterfacer):

    def __init__(self, name, gateway_ip="127.0.0.1", local_ip="127.0.0.1", port=3671):
        """Initialize Interfacer

        """
        # Initialization
        super(EmonHubKNXInterfacer, self).__init__(name)

        # Interfacer specific settings
        self._KNX_settings = {'read_interval': 10.0,
                               'nodename':'KNX',
                               'validate_checksum': True,
                               'meters':[]}

        self._last_read_time = 0

        try:
            self.loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._run_loop, name=f"{name}-asyncio", daemon=True)
            self._loop_thread.start()

            fut = asyncio.run_coroutine_threadsafe(self.initKnx(gateway_ip, local_ip), self.loop)
            fut.result()  # raise si erreur

            self.cargoList = {}

        except ModuleNotFoundError as err:
            self._log.error(err)
            self.ser = False


    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def action(self):
        super().action()


    async def initKnx(self, gateway_ip, local_ip):
        connection_config = ConnectionConfig(
                                        connection_type=ConnectionType.TUNNELING,
                                        gateway_ip=gateway_ip,
                                        local_ip = local_ip
        )

        self._log.debug("Connect to KNX Gateway : " + gateway_ip)
        self.xknx = XKNX(connection_config=connection_config,   connection_state_changed_cb = self.connection_state_changed_cb,device_updated_cb=self.device_updated_cb, daemon_mode=False)

    async def startKnx(self):
        try:
            await self.xknx.start()
        except Exception as err: 
            self._log.error("KNX Error start:")
            self._log.error(err);

    def connection_state_changed_cb(self, state):
        self._log.debug("KNX CnxUpdate:" )
        self._log.debug(state)
        

    def device_updated_cb(self, device):
        value = device.resolve_state()
        name = device.name
        unit = device.unit_of_measurement()

        pos = name.index("_")
        meter = name[0:pos]
        key = name[pos+1:]

        meterObj=self._settings['meters'][meter]
        dptConf = meterObj[key]
        if 'divider' in dptConf:
            divider = dptConf["divider"]
            if divider != '':
                value = float(value) / float(divider)



        result = {}
        result[key] = [value,unit]


        if meter in self.cargoList:
            c = self.cargoList[meter]
            self.add_result_to_cargo(c, result)
        else:
            cargoNew = Cargo.new_cargo("", False,[], [])
            cargoNew.nodeid = meter
            self.cargoList[meter] = cargoNew
            self.add_result_to_cargo(cargoNew, result)



    def add_result_to_cargo(self, cargo, result):
        if result != None:

            for key in result:
                cargo.names.append(key)
                cargo.realdata.append(result[key][0])
        else:
            self._log.info("Decoded KNX data: None")


    async def setupSensor(self):
        metters = self._settings['meters']

        self.sensor={}
        for metter in metters:
            dpPoint = metters[metter]

            for dpKey in dpPoint:
                dpConfig = dpPoint[dpKey]

                group = dpConfig["group"]
                eis = dpConfig["eis"]

                self._log.debug("add Sensors:" + metter+"_"+dpKey + ' <> ' + group)
                self.sensor[metter+"_"+dpKey] = Sensor(self.xknx, metter + "_" + dpKey, value_type=eis, group_address_state=group, always_callback=True)
                self.xknx.devices.async_add(self.sensor[metter+"_"+dpKey])




    def add(self, cargo):
        self.buffer.storeItem(cargo)


    async def waitSensor(self):
        pass


    def read(self):
        """Read data and process

        Return data as a list: [NodeID, val1, val2]

        """
        
        interval = int(self._settings['read_interval'])
        if time.time() - self._last_read_time < interval:
            return

        
        self._last_read_time = time.time()

        result = self.cargoList;
        self.cargoList ={};

        return result;

    def start(self):
        self._log.info("Start KNX interface")

        # Setup sensors + start KNX dans la loop
        asyncio.run_coroutine_threadsafe(self.setupSensor(), self.loop).result()
        asyncio.run_coroutine_threadsafe(self.startKnx(), self.loop).result()

        super().start()
        
    def close(self):
        # si EmonHub appelle close/stop, tu peux stopper proprement
        self._stop_evt.set()
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

    def set(self, **kwargs):
        for key, setting in self._KNX_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._KNX_settings[key]

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
            elif key == 'validate_checksum':
                self._log.info("Setting %s validate_checksum: %s", self.name, setting)
                self._settings[key] = True
                if setting=='False':
                    self._settings[key] = False
                continue
            elif key == 'meters':
                self._log.info("Setting %s meters: %s", self.name, json.dumps(setting))
                self._settings['meters'] = {}
                for meter in setting:
                    # default
                    address = 1
                    meter_type = "standard"
                    records = []

                    self._settings['meters'][meter] = setting[meter]
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)



    class Updater(threading.Thread):
        def __init__(self,  knxIntf):
            super().__init__()
            self.loop = asyncio.get_event_loop()
            self.knxIntf = knxIntf

            pass

        def run(self):
            while not self.knxIntf.stop:
                self.loop.run_until_complete(asyncio.sleep(1))
            pass
