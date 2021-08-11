import time
import json
import Cargo
import serial
import struct
from emonhub_interfacer import EmonHubInterfacer

"""
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device = /dev/ttyAMA0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = MBUS
        [[[[meters]]]]
            [[[[[sdm120]]]]]
                address = 1
                type = sdm120
            [[[[[qalcosonic]]]]]
                address = 2
                type = qalcosonic_e3
"""

"""class EmonHubMBUSInterfacer

MBUS interfacer for use in development

"""

class EmonHubMBUSInterfacer(EmonHubInterfacer):

    def __init__(self, name, device="/dev/ttyUSB0", baud=2400, use_meterbus_lib=False):
        """Initialize Interfacer

        """
        # Initialization
        super(EmonHubMBUSInterfacer, self).__init__(name)

        # This line will stop the default values printing to logfile at start-up
        # self._settings.update(self._defaults)

        # Interfacer specific settings
        self._MBUS_settings = {'read_interval': 10.0,
                               'nodename':'MBUS',
                               'validate_checksum': True,
                               'meters':[]}

        self.next_interval = True

        # Only load module if it is installed
        try:
            self._log.debug("Connecting to MBUS serial: " + device + " " + str(baud))
            self.ser = serial.Serial(device, baud, 8, 'E', 1, 0.5)
        except ModuleNotFoundError as err:
            self._log.error(err)
            self.ser = False
            
        # If use_meterbus_lib is true, try to load module
        # pip3 install pyMeterBus
        self.use_meterbus_lib = False
        if use_meterbus_lib:
            try:
                from pyMeterBus import meterbus
                self.meterbus = meterbus
                self.use_meterbus_lib = True
            except ModuleNotFoundError as err:
                self._log.error(err)
                self.use_meterbus_lib = False

    def mbus_short_frame(self, address, C_field):
        data = [0x10,C_field,address,0x0,0x16]
        data[3] = (data[1]+data[2]) % 256
        self.ser.write(data)

    def mbus_set_address(self, old_address, new_address):
        data = [0x68,0x06,0x06,0x68,0x53,old_address,0x51,0x01,0x7A,new_address,0x0,0x16]
        data = self.checksum(data)
        self.ser.write(data)
        
    def mbus_set_baudrate(self, address, baudrate):
        baudrate_hex = 0xBB # default is 2400
        if baudrate==300: baudrate_hex = 0xB8
        if baudrate==600: baudrate_hex = 0xB9
        if baudrate==1200: baudrate_hex = 0xBA
        if baudrate==2400: baudrate_hex = 0xBB
        if baudrate==4800: baudrate_hex = 0xBC
        if baudrate==9600: baudrate_hex = 0xBD
    
        data = [0x68,0x03,0x03,0x68,0x53,address,baudrate_hex,0x0,0x16]
        data = self.checksum(data)
        self.ser.write(data)

    # Does not seem to work yet on SDM120MB
    def check_secondary_address(self, a2a,a2b,a2c,a2d):
        data = [0x68,0x0B,0x0B,0x68,0x73,0xFD,0x52,a2d,a2c,a2b,a2a,0xFF,0xFF,0xFF,0xFF,0x0,0x16]
        data = self.checksum(data)
        self.ser.write(data)
        
    def mbus_request(self, address, telegram):
        data = [0x68,0x07,0x07,0x68,0x53,address,0x51,0x01,0xFF,0x08,telegram,0x0,0x16]
        data = self.checksum(data)
        self.ser.write(data)

    def mbus_request_sdm120(self, address):
        data = [0x68,0x03,0x03,0x68,0x53,address,0xB1,0x0,0x16]
        data = self.checksum(data)
        self.ser.write(data)

    def checksum(self,data):
        checksum = 0
        for c in range(4, len(data)-2):
            checksum += data[c]
        data[len(data)-2] = checksum % 256
        return data

    def set_page(self, address, page):
        for retry in range(10):
            self.mbus_request(address, page)
            time.sleep(0.3)
            if self.ser.in_waiting and ord(self.ser.read(1)) == 0xE5:
                self._log.debug("ACK")
                time.sleep(0.5)
                return True
            else:
                time.sleep(0.2)
        return False

    def decodeBCD(self, bcd_data):
        val = 0
        i = len(bcd_data)
        while i > 0:
            val = val * 10
            if bcd_data[i-1] >> 4 < 0xA:
                val += (bcd_data[i-1] >> 4) & 0xF
            val = (val * 10) + (bcd_data[i-1] & 0xF)
            i -= 1
        if bcd_data[-1] >> 4 == 0xF:
            val *= -1
        return val

    def decodeInt(self,bytes):
        if len(bytes) == 1:
            return bytes[0]
        if len(bytes) == 2:
            return struct.unpack("h", bytearray(bytes))[0]
        if len(bytes) == 3:
            return bytes[0] + (bytes[1]<<8) + (bytes[2]<<16)
        if len(bytes) == 4:
            return struct.unpack("i", bytearray(bytes))[0]
        return False

    def parse_frame(self,data,records):
        data_types =   ['null','int','int','int','int','float','int','int','null','bcd','bcd','bcd','bcd','var','bcd','null']
        data_lengths = [0,1,2,3,4,4,6,8,0,1,2,3,4,6,6,0]
        vif = {
            0x03: (0.001, "Energy", "kWh"),
            0x04: (0.01, "Energy", "kWh"),
            0x05: (0.1, "Energy", "kWh"),
            0x06: (1, "Energy", "kWh"),
            0x13: (0.001, "Volume", "m3"),
            0x14: (0.01, "Volume", "m3"),
            0x15: (0.1, "Volume", "m3"),
            0x16: (1, "Volume", "m3"),
            0x17: (10, "Volume", "m3"),
            0x20: (1, "Ontime", "s"),
            #0x22: (1, "Ontime Hours", "h"),
            0x24: (1, "OperatingTime", "s"),
            0x2a: (0.1, "Power", "W"),
            0x2b: (1, "Power", "W"),
            0x2e: (1000, "Power", "W"),
            0x3b: (0.001, "FlowRate", "m3/h"), # mm3/h
            0x3c: (0.01, "FlowRate", "m3/h"), # mm3/h
            0x3d: (0.1, "FlowRate", "m3/h"), # mm3/h
            0x3e: (1, "FlowRate", "m3/h"), # m3/h
            # 0x40: (0.06, "FlowRate", "m3/h"), # 1.0e-7 m3/min
            0x59: (0.01, "FlowT", "C"),
            0x5a: (0.1, "FlowT", "C"),
            0x5b: (1, "FlowT", "C"),
            0x5d: (0.01, "ReturnT", "C"),
            0x5e: (0.1, "ReturnT", "C"),
            0x5f: (1, "ReturnT", "C"),
            0x61: (0.01, "DeltaT", "C"),
            0x62: (0.1, "DeltaT", "C"),
            0x63: (1, "DeltaT", "C"),
            0x67: (1, "ExternalT", "C"),

            0x6d: (1, "DateTime", ""),
            #0x70: (1, "Average duration", ""),
            #0x74: (1, "Duration seconds actual", ""),
            #0x75: (1, "Duration minutes actual", ""),
            #0x78: (1, "Fab No", ""),
            #0x79: (1, "Enhanced", "")
            0x84: (10, "Energy", "Wh"),
            0x78: (1,"FabNo",""),
            0x7f: (1,"ManSpec","")
            # 0xfd: (1, "Extended", "")
        }
        vife = {
            0x47: (0.01, "Voltage", "V"),  # SDM120
            0x59: (0.001, "Current", "A"), # SDM120
            0x3a: (0.01, "Frequency", "Hz"), # SDM120
            0x3b: (1, "Energy", "kWh"),    # Qalcosonic
            0x3c: (1, "Cooling", "kWh"),   # Qalcosonic
        }
        
        function_types = ["","Max","Min","error","special","special","more_to_follow"]

        header = ["START","LEN","LEN","START","C FIELD","ADDRESS","CI FIELD","ID","ID","ID","ID","MID","MID","GEN","MEDIA","ACCESS","ACCESS","SIGNATURE","SIGNATURE"]

        checksum = 0
        next = 'START'
        length = 0
        bid_end = len(data)-1
        bid_checksum = len(data)-2

        result = {}
        name_count = {}
        record = 0
        
        debug = False

        for bid in range(0,len(data)):
            this = next

            val = data[bid]
            if debug: print(bid,end='\t')
            if debug: print(val,end='\t')
            if debug: print(hex(val),end='\t')
            
            # Header info for debug
            if bid<len(header): this = header[bid]
            
            # Start
            if bid==0 and val!=0x68: this += " INVALID"
            # Length
            if bid==1:
                length = val
                bid_end = length+4+2-1
                bid_checksum = bid_end-1
            # Length
            if bid==2 and val!=length: this += " INVALID"
            # Start repeat
            if bid==3 and val!=0x68: this += " INVALID"

            # Checksum
            if bid>3 and bid<bid_checksum:
                checksum += val

            if bid==bid_checksum:
                this = "CHECKSUM"
                if val!=checksum%256:
                    this += " INVALID"
            
            if bid==bid_end and val==0x16: this = "END"

            if debug: print(this,end=' \t')

            if bid==18:
                if debug: print("\n-----------------------------------------",end='\t')
                next = 'DIF'

            if bid>=19 and bid<len(data):
                
                if this=='DIF':
                    DIF = val
                    if DIF>=0x80: next='DIFE'
                    else: next='VIF'
                        
                    data_count = 0
                    data_field = DIF & 0x0F
                    data_len = data_lengths[data_field]
                    data_type = data_types[data_field]

                    function = (DIF & 0x30) >> 4
                    if function < len(function_types):
                        function = function_types[function]
                    else:
                        function = ""

                    if debug: print(str(data_type)+"("+str(data_len)+") "+str(function)+" "+str(record+1),end='\t')
                    
                    name = ""
                    scale = 1
                    unit = ""

                if this=='DIFE':
                    if val>=0x80: next='DIFE' 
                    else: next='VIF'
                    
                if this=='VIF':
                    VIF = val
                    if VIF in vif:
                        scale = vif[VIF][0]
                        name = vif[VIF][1]                
                        unit = vif[VIF][2]
                        if debug: print(name,end='\t')
                    
                    if val>=0x80: next='VIFE'
                    else: next='DATA'
                  
                if this=='VIFE':
                    VIFE = val
                    if VIFE in vife:
                        scale = vife[VIFE][0]
                        name = vife[VIFE][1]                
                        unit = vife[VIFE][2]
                        if debug: print(name,end='\t')
                              
                    if val>=0x80: next='VIFE'
                    else: next='DATA'

                if this=='DATA':
                    data_count = data_count + 1
                    if data_count==data_len:
                    
                      bytes = data[bid-data_len+1:bid+1]
                      if data_type == "int": value = self.decodeInt(bytes)

                      if data_type == "float":
                          if data_len == 4:
                              value = struct.unpack("f", bytearray(bytes))[0]

                      if data_type == "bcd":
                          value = self.decodeBCD(bytes)
                      
                      if debug: print(str(value*scale)+" "+str(unit),end='\t')
                      record = record + 1
                      
                      # --------------------------
                      if name=="": name = "Record"
                      # Apply function 
                      if function != '':
                          name += "_" + function
                      # Count variables with same name
                      if name not in name_count:
                          name_count[name] = 0
                      name_count[name] += 1
                      # Apply name index
                      if name != "Record":
                          if name in result:
                              name += str(name_count[name])
                      else: 
                          name += str(record)
                      # --------------------------
                      
                      if record in records or len(records)==0:
                          result[name] = [value*scale,unit]
                      if debug: print("\n-----------------------------------------",end='\t')
                      next='DIF'
            
            if debug: print()

        if 'FlowT' in result and 'ReturnT' in result and 'FlowRate' in result:
            value = 4150 * (result['FlowT'][0] - result['ReturnT'][0]) * (result['FlowRate'][0] * (1000 / 3600))
            result['heat_calc'] = [value, "W"]

        return result

    def parse_frame_meterbus_lib(self,data,records):
        telegram = self.meterbus.load(data)
        meterbus_obj = json.loads(telegram.to_JSON())
        
        result = {}
        for record in meterbus_obj['body']['records']:
            if type(record['value'])==int or type(record['value'])==float:
                name = record['type'].replace('VIFUnit.','').replace('VIFUnitExt.','').lower()
                value = record['value']
                unit = record['unit'].replace('MeasureUnit.','')
                result[name] = [value, unit]
            
        return result

    def request_data(self, address, records):
        for i in range(0,2):
            self.mbus_short_frame(address, 0x5b)
            # time.sleep(1.0)
            result = self.read_data_frame(records)
            if result!=None:
                return result
            else:
                time.sleep(0.2) 

    def request_data_sdm120(self, address, records):
        for i in range(0,2):
            self.mbus_request_sdm120(address)
            # time.sleep(1.0)
            result = self.read_data_frame(records)
            if result!=None:
                return result
            else:
                time.sleep(0.2) 


    def read_data_frame(self,records):
        data = []
        bid = 0
        bid_end = 255
        bid_checksum = 255
        checksum = 0
        valid = False
        
        start_time = time.time()
        
        val = 0
        
        while (time.time()-start_time)<2.0:
            while self.ser.in_waiting:
                # Read in byte
                val = ord(self.ser.read(1))
                data.append(val)
                # print(str(bid)+" "+str(val)+" "+str(hex(val)))
                # Long frame start, reset checksum
                if bid == 0 and val == 0x68:
                    # print("MBUS start")
                    valid = True
                    checksum = 0

                # 2nd byte is the frame length
                if valid and bid == 1:
                    length = val
                    bid_end = length + 4 + 2 - 1
                    bid_checksum = bid_end - 1
                    # print("MBUS length "+str(length))
                    # print("MBUS bid_end "+str(bid_end))
                    # print("MBUS bid_checksum "+str(bid_checksum))

                if valid and bid == 2 and val != length:
                    valid = False                       # 3rd byte is also length, check that its the same as 2nd byte
                if valid and bid == 3 and val != 0x68:
                    valid = False                         # 4th byte is the start byte again
                if valid and bid > 3 and bid < bid_checksum:
                    checksum += val                 # Increment checksum during data portion of frame

                if valid and bid == bid_checksum and val != checksum % 256:
                    if self._settings['validate_checksum']: 
                        valid = False  # Validate checksum
                        
                if bid == bid_end and val == 0x16:
                    time_elapsed = time.time()-start_time
                    self._log.debug("Invalid MBUS data received %d bytes %0.1f ms" % (bid,time_elapsed*1000))
                            
                    if valid: # Parse frame if still valid
                        if self.use_meterbus_lib:
                            return self.parse_frame_meterbus_lib(data,records)
                        else:
                            return self.parse_frame(data,records)

                bid += 1
            time.sleep(0.1)
            
        # If we are here data response is corrupt
        time_elapsed = time.time()-start_time
        self._log.debug("Invalid MBUS data received %d bytes %0.1f ms" % (bid,time_elapsed*1000))       
        # end of read_data_frame

    def add_result_to_cargo(self,meter,c,result):
        if result != None:
            self._log.debug("Decoded MBUS data: " + json.dumps(result))

            for key in result:
                c.names.append(meter+"_"+key)
                c.realdata.append(result[key][0])
                c.units.append(result[key][1])
        else:
            self._log.debug("Decoded MBUS data: None")
        return c
    
    

    def read(self):
        """Read data and process

        Return data as a list: [NodeID, val1, val2]

        """

        if int(time.time()) % self._settings['read_interval'] == 0:
            if self.next_interval:
                self.next_interval = False

                c = Cargo.new_cargo()
                c.names = []
                c.realdata = []
                c.units = []
                c.nodeid = self._settings['nodename']
                
                # Support for multiple MBUS meters on a single bus
                for meter in self._settings['meters']:
                    
                    address = self._settings['meters'][meter]['address']
                    meter_type = self._settings['meters'][meter]['type']
                
                    # Most mbus meters use standard request, page 0 or default, all records
                    if meter_type=="standard":
                        result = self.request_data(address,[])
                        self.add_result_to_cargo(meter,c,result)

                    # Qalcosonic E3
                    if meter_type=="qalcosonic_e3":
                        result = self.request_data(address,[4,5,6,7,8,9,10,11,12,13,14,15])
                        self.add_result_to_cargo(meter,c,result) 

                    # ------------------------------------------------------
                    # Sontex Multical 531
                    if meter_type=="sontex531":
                        # p1
                        self.set_page(address, 1)
                        result = self.request_data(address,[4,5])
                        self.add_result_to_cargo(meter,c,result)
                        # p3
                        self.set_page(address, 3)                     
                        result = self.request_data(address,[1,2,3,4])
                        self.add_result_to_cargo(meter,c,result)                            
                            
                    # SDM120 special request command
                    elif meter_type=="sdm120":
                        # 1. Get energy data
                        result = self.request_data(address,[1])
                        self.add_result_to_cargo(meter,c,result)                       
                        # 2. Get instantaneous data
                        result = self.request_data_sdm120(address,[1,7,11,23])
                        self.add_result_to_cargo(meter,c,result)
                    # ------------------------------------------------------
                            

                            
                if len(c.realdata) > 0:
                    return c

        else:
            self.next_interval = True

        return False


    def set(self, **kwargs):
        for key, setting in self._MBUS_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._MBUS_settings[key]

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
                    
                    # address
                    if 'address' in setting[meter]:
                        address = int(setting[meter]['address'])
                    # type e.g sdm 
                    if 'type' in setting[meter]:
                        meter_type = str(setting[meter]['type'])
                    #assign
                    self._settings['meters'][meter] = {
                        'address':address,
                        'type':meter_type,
                    }
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)
