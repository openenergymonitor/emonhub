import time
import json
import Cargo
import os
import serial.tools.list_ports

import glob
from emonhub_interfacer import EmonHubInterfacer


"""
[[SDM120]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 2400
        parity = none
        datatype = float
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sdm120
        # prefix = sdm_
        [[[[meters]]]]
            [[[[[sdm120a]]]]]
                address = 1
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
            [[[[[sdm120b]]]]]
                address = 2
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3

[[SAMSUNG-ASHP-MIB19N]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 9600
        parity = even
        datatype = int
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 20
        nodename = samsung-ashp
        # prefix = sdm_
        [[[[meters]]]]
            [[[[[ashp]]]]]
                device_type = samsung
                address = 1
                registers = 75,74,72,65,66,68,52,59,58,2,79,87,5,89
                names = dhw_temp,dhw_target,dhw_status,return_temp,flow_temp,flow_target,heating_status,indoor_temp,indoor_target, defrost_status,away_status,flow_rate,outdoor_temp,3_way_valve
                scales = 0.1,0.1,1,0.1,0.1,0.1,1,0.1,0.1,1,1,0.1,0.1,1
                precision = 2,2,1,2,2,2,1,2,2,1,1,2,2,1
   
[[SDM630]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB1
        baud = 9600
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sdm630
        # prefix = sdm_
        registers = 0,1,2,3,4,5,6,7,8,26,36,37
        names =  V1,V2,V3,I1,I2,I3,P1,P2,P3,TotalPower,Import_kWh,Export_kWh
        precision = 2,2,2,2,2,2,2,2,2,2,2,2

"""

"""class EmonHubSDM120Interfacer

SDM120 interfacer for use in development

"""

class EmonHubMinimalModbusInterfacer(EmonHubInterfacer):

    def __init__(self, name, device="/dev/modbus", device_vid=False, device_pid=False, baud=2400, parity="none", datatype="float"):
        """Initialize Interfacer

        """
        # Initialization
        super(EmonHubMinimalModbusInterfacer, self).__init__(name)

        # This line will stop the default values printing to logfile at start-up
        # self._settings.update(self._defaults)

        # Interfacer specific settings
        self._modbus_settings = {
            'read_interval': 10.0,
            'nodename':'sdm120',
            'prefix':'',
            'meters':[]
        }
        
        self.next_interval = True
        
        # Only load module if it is installed
        self._rs485 = False
        try:
            import minimalmodbus
            self.minimalmodbus = minimalmodbus
            # import serial
        except ModuleNotFoundError as err:
            self._log.error(err)
            self._rs485 = False
        
        self.device = device
        self.device_vid = device_vid
        self.device_pid = device_pid

        self.baud = baud
        self.parity = parity
        self.datatype = datatype
        self.rs485_connect()  
                    
    def rs485_connect(self):

        device = False

        # List available ports
        ports = serial.tools.list_ports.comports()
        for port in ports:

            # if self.device ends with * then filter devices by matching self.device up to the *
            if self.device[-1] == "*":
                if not port.device.startswith(self.device[:-1]):
                    continue
            else:
                if port.device != self.device:
                    continue

            # if device_vid filter by vid
            if self.device_vid:
                if port.vid != int(self.device_vid):
                    continue

            # if device_pid filter by pid
            if self.device_pid:
                if port.pid != int(self.device_pid):
                    continue

            # print port details
            self._log.info("Modbus device found: %s, vid:%s, pid:%s" % (port.device, port.vid, port.pid))
            device = port.device

        # check for valid symbolic link
        if not device:
            if os.path.islink(self.device):
                device = self.device

        # if device is still False, log error and return False
        if not device:
            self._log.error("Could not find Modbus device")
            self.ser = False
            return False

        try:
            self._log.info("Connecting to Modbus device="+str(device)+" baud="+str(self.baud)+" parity="+str(self.parity)+" datatype="+str(self.datatype))
            
            self._rs485 = self.minimalmodbus.Instrument(device, 1)
            self._rs485.serial.baudrate = self.baud
            self._rs485.serial.bytesize = 8
            if self.parity == 'even':
                self._rs485.serial.parity = self.minimalmodbus.serial.PARITY_EVEN
            elif self.parity == 'odd':
                self._rs485.serial.parity = self.minimalmodbus.serial.PARITY_ODD
            elif self.parity == 'mark':
                self._rs485.serial.parity = self.minimalmodbus.serial.PARITY_MARK
            elif self.parity == 'space':
                self._rs485.serial.parity = self.minimalmodbus.serial.PARITY_SPACE
            else:
                self._rs485.serial.parity = self.minimalmodbus.serial.PARITY_NONE
            self._rs485.serial.stopbits = 1
            self._rs485.serial.timeout = 1
            self._rs485.debug = False
            self._rs485.mode = self.minimalmodbus.MODE_RTU
        except Exception:
            self._log.error("Could not connect to Modbus device")
            self._rs485 = False

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
             
                if self._rs485:
                    invalid_count = 0
                    register_count = 0
                    
                    # Support for multiple MBUS meters on a single bus
                    for meter in self._settings['meters']:
                        
                        self._rs485.address = self._settings['meters'][meter]['address']
                        
                        if self._settings['meters'][meter]['device_type'] == 'samsung':
                            self._log.debug("Samsung device active")
                            # map Flow rate (l/min), OutdoorT, 3-way valve 0=CH 1=DHW, Compressor controll %, Compressor freq (Hz), Immersion heater status
                            self._rs485.write_registers(7005,[0x42E9, 0x8204, 0x4067, 0x42F1, 0x8238, 0x4087])
                            
                        for i in range(0,len(self._settings['meters'][meter]['registers'])):
                            register_count += 1
                            valid = True
                            try:
                                # Get functioncode if provided, else default
                                functioncodes = self._settings['meters'][meter].get('functioncodes', [])
                                if i < len(functioncodes):
                                    functioncode = int(functioncodes[i])
                                else:
                                    if self.datatype == 'int':
                                        functioncode = 3
                                    else:
                                        functioncode = 4

                                if self.datatype == 'int':
                                    time.sleep(0.1)
                                    value = self._rs485.read_register(
                                        int(self._settings['meters'][meter]['registers'][i]),
                                        functioncode=functioncode, signed=True)
                                elif self.datatype == 'float':
                                    time.sleep(0.1)
                                    value = self._rs485.read_float(
                                        int(self._settings['meters'][meter]['registers'][i]),
                                        functioncode=functioncode, number_of_registers=2)
                                else:
                                    time.sleep(0.1)
                                    value = self._rs485.read_float(
                                        int(self._settings['meters'][meter]['registers'][i]),
                                        functioncode=functioncode, number_of_registers=2)
                            
                                    
                            except Exception as e:
                                valid = False
                                invalid_count += 1
                                self._log.error("Could not read register @ "+str(self._settings['meters'][meter]['registers'][i])+": " + str(e))
                            
                            if valid:
                                # replace datafield name with custom name
                                if i<len(self._settings['meters'][meter]['names']):
                                    name = self._settings['meters'][meter]['names'][i]
                                else:
                                    name = "r"+str(self._settings['meters'][meter]['registers'][i])
                                # apply rounding if set
                                if i<len(self._settings['meters'][meter]['precision']):
                                    value = round(value,int(self._settings['meters'][meter]['precision'][i]))
                                # apply scales
                                if i<len(self._settings['meters'][meter]['scales']) and self._settings['meters'][meter]['scales'][i] is not None:
                                    value = value*self._settings['meters'][meter]['scales'][i]
                                c.names.append(self._settings['prefix']+str(meter)+"_"+name)
                                c.realdata.append(value)
                                # self._log.debug(str(name)+": "+str(value))
                                
                        time.sleep(0.1)
                        
                    if invalid_count==register_count:
                        self._log.error("Could not read all registers")
                        self.rs485_connect()
                           
                    if len(c.realdata)>0:
                        self._log.debug(c.realdata)
                        return c
                else:
                     self._log.error("Not connected to modbus device")
                     self.rs485_connect()
                    
        else:
            self.next_interval = True
            
        return False


    def set(self, **kwargs):
        for key, setting in self._modbus_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._modbus_settings[key]
                
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
            elif key == 'prefix':
                self._log.info("Setting %s prefix: %s", self.name, setting)
                self._settings[key] = str(setting)
                continue
            elif key == 'meters':
                self._settings['meters'] = {}
                for meter in setting:
                    # default
                    device_type = []
                    address = 1
                    registers = []
                    names = []
                    precision = []
                    scales = []
                    functioncodes = []
                    # address
                    if 'device_type' in setting[meter]:
                        device_type = setting[meter]['device_type']
                        self._log.info("Setting %s meters %s device_type %s", self.name, meter, device_type)
                        
                    if 'address' in setting[meter]:
                        address = int(setting[meter]['address'])
                        self._log.info("Setting %s meters %s address %s", self.name, meter, address)
                        
                    if 'registers' in setting[meter]:
                        for reg in setting[meter]['registers']:
                            registers.append(int(reg))
                        self._log.info("Setting %s meters %s registers %s", self.name, meter, json.dumps(registers))
                                                   
                    if 'names' in setting[meter]:
                        for name in setting[meter]['names']:
                            names.append(str(name))
                        self._log.info("Setting %s meters %s names %s", self.name, meter, json.dumps(names))
                        
                    if 'precision' in setting[meter]:
                        for dp in setting[meter]['precision']:
                            precision.append(int(dp))
                        self._log.info("Setting %s meters %s precision %s", self.name, meter, json.dumps(precision))
                        
                    if 'scales' in setting[meter]:
                        for scale in setting[meter]['scales']:
                            scales.append(float(scale))
                        self._log.info("Setting %s meters %s scales %s", self.name, meter, json.dumps(scales))
                        
                    if 'functioncodes' in setting[meter]:
                        for fc in setting[meter]['functioncodes']:
                            functioncodes.append(int(fc))
                        self._log.info("Setting %s meters %s functioncodes %s", self.name, meter, json.dumps(functioncodes))
                    #assign
                    self._settings['meters'][meter] = {
                        'device_type':device_type,
                        'address':address,
                        'registers':registers,
                        'names':names,
                        'precision':precision,
                        'scales':scales,
                        'functioncodes':functioncodes
                    }
                    
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)

