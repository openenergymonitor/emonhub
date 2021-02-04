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
        device = /dev/ttyUSB0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        address = 100
        pages = 0,
        read_interval = 10
        nodename = MBUS
"""

"""class EmonHubMBUSInterfacer

MBUS interfacer for use in development

"""

class EmonHubMBUSInterfacer(EmonHubInterfacer):

    def __init__(self, name, device="/dev/ttyUSB0", baud=2400):
        """Initialize Interfacer

        """
        # Initialization
        super(EmonHubMBUSInterfacer, self).__init__(name)

        # This line will stop the default values printing to logfile at start-up
        # self._settings.update(self._defaults)

        # Interfacer specific settings
        self._MBUS_settings = {'address': 100, 'pages': [0], 'read_interval': 10.0,'nodename':'MBUS'}
        
        self.next_interval = True
        
        # Only load module if it is installed        
        try: 
            self._log.debug("Connecting to MBUS serial: "+device+" "+str(baud))
            self.ser = serial.Serial(device, baud, 8, 'E', 1, 0.5)
        except ModuleNotFoundError as err:
            self._log.error(err)
            self.ser = False
                    

    def mbus_short_frame(self, address, C_field):
        data = [0]*5
        data[0] = 0x10
        data[1] = C_field
        data[2] = address
        data[3] = data[1]+data[2]
        data[4] = 0x16
        self.ser.write(data)

    def mbus_request(self, address, telegram):
        data = [0]*13
        data[0] = 0x68
        data[1] = 0x07
        data[2] = 0x07
        data[3] = 0x68
        
        data[4] = 0x53
        data[5] = address
        data[6] = 0x51

        data[7] = 0x01
        data[8] = 0xFF
        data[9] = 0x08
        data[10] = telegram

        checksum = 0
        for c in range(4,11): checksum += data[c]
        data[11] = checksum % 256
        
        data[12] = 0x16
        
        self.ser.write(data)

    def set_page(self, address, page):
        for retry in range(10):
            self.mbus_request(address,page)
            time.sleep(0.3)
            if self.ser.in_waiting and ord(self.ser.read(1))==0xE5: 
                self._log.debug("ACK")
                time.sleep(0.5)
                return True
            else:
                time.sleep(0.2)
        return False

    def decodeBCD(self,bcd_data):
        val = 0
        i = len(bcd_data)
        while i > 0:
            val = (val * 10)
            if bcd_data[i-1]>>4 < 0xA:
                val += ((bcd_data[i-1]>>4) & 0xF)
            val = (val * 10) + ( bcd_data[i-1] & 0xF)
            i -= 1
        if(bcd_data[len(bcd_data)-1]>>4 == 0xF):
            val *= -1
        return val
    
    def parse_frame(self,data):
        data_types =   ['null','int','int','int','int','float','int','int','null','bcd','bcd','bcd','bcd','var','bcd','null']
        data_lengths = [0,1,2,3,4,4,6,8,0,1,2,3,4,6,6,0]
        vif = {
            0x03: (0.001,"Energy","kWh"),
            0x06: (1,"Energy","kWh"),
            0x13: (0.001,"Volume","m3"),
            0x14: (0.01,"Volume","m3"),
            0x15: (0.1,"Volume","m3"),
            0x16: (1,"Volume","m3"),
            0x20: (1,"Ontime","s"),
            #0x22: (1,"Ontime Hours","h"),
            0x24: (1,"OperatingTime","s"),
            0x2b: (1,"Power","W"),
            0x2e: (1000,"Power","W"),
            0x3b: (0.001,"FlowRate","m3/h"), # mm3/h
            0x3c: (0.01,"FlowRate","m3/h"), # mm3/h
            0x3d: (0.1,"FlowRate","m3/h"), # mm3/h
            0x3e: (1,"FlowRate","m3/h"), # m3/h
            # 0x40: (0.06,"FlowRate","m3/h"), # 1.0e-7 m3/min
            0x59: (0.01,"FlowT","C"),
            0x5a: (0.1,"FlowT","C"),
            0x5b: (1,"FlowT","C"),
            0x5d: (0.01,"ReturnT","C"),
            0x5e: (0.1,"ReturnT","C"),
            0x5f: (1,"ReturnT","C"),
            0x61: (0.01,"DeltaT","C"),
            0x62: (0.1,"DeltaT","C"),
            0x63: (1,"DeltaT","C"),
            0x67: (1,"ExternalT","C"),
            #0x6D: (1,"TIME & DATE",""),
            #0x70: (1,"Average duration",""),
            #0x74: (1,"Duration seconds actual",""),       
            #0x75: (1,"Duration minutes actual",""),
            #0x78: (1,"Fab No",""),
            #0x79: (1,"Enhanced","")
            0x84: (10,"Energy","Wh")
        }
        function_types = ["","Max","Min","error","special","special","more_to_follow"]

        result = {}
        bid = 19
        record = 0
        while bid<len(data)-1:
        
            record += 1
            
            DIF = data[bid]
            bid += 1
            DIFE = 0
            if DIF>=0x80:
                DIFE = data[bid]
                bid += 1
                
            VIF = data[bid]
            bid += 1 
            VIFE = 0
            if VIF>=0x80:
                VIFE = data[bid]
                bid += 1

            data_field = DIF & 0x0F # AND logic
            
            function = (DIF & 0x30) >> 4
            if function<len(function_types):
                function = function_types[function]
            else:
                function = ""
            
            data_type = data_types[data_field]
            data_len = data_lengths[data_field]
            
            if data_len>0:
                bytes = data[bid:bid+data_len]
                
                if len(bytes)==data_len:

                    bid += data_len

                    vif_name = ""
                    if VIF in vif:
                        scale = vif[VIF][0]
                        name = vif[VIF][1]
                        unit = vif[VIF][2]

                        if function!='': name += "_"+function

                        value = False

                        if data_type=="int":
                            if data_len==1:
                                value = bytes[0]
                            if data_len==2:
                                value = bytes[0] + (bytes[1]<<8)
                            if data_len==3:
                                value = bytes[0] + (bytes[1]<<8) + (bytes[2]<<16)    
                            if data_len==4:
                                value = bytes[0] + (bytes[1]<<8) + (bytes[2]<<16) + (bytes[3]<<24)

                        if data_type=="float":
                            if data_len==4:
                                value = struct.unpack("f",bytearray(bytes))[0]
                                
                        if data_type=="bcd":
                            value = self.decodeBCD(bytes)
                                
                        value *= scale

                        #self._log.debug(hex(DIF)+"\t"+hex(DIFE)+"\t"+hex(VIF)+"\t"+hex(VIFE)+"\t"+data_type+str(data_len)+"\t"+" ["+",".join(map(str, bytes))+"] "+name+" = "+str(value)+" "+str(unit))
                        #self._log.debug(vif_name+" "+function+" = "+str(value)+" "+str(unit))

                        if name in result:
                            name += str(record)

                        result[name] = [value,unit]
                
        if 'FlowT' in result and 'ReturnT' in result and 'FlowRate' in result:
            value = 4150 * (result['FlowT'][0] - result['ReturnT'][0]) * (result['FlowRate'][0] * (1000 / 3600))        
            result['heat_calc'] = [value,"W"]
            
        return result

    def request_data(self,address):
        self.mbus_short_frame(address,0x5b)
        time.sleep(0.5)

        data = []
        bid = 0
        bid_end = 255
        bid_checksum = 255
        checksum = 0
        valid = False
        
        while self.ser.in_waiting:
            # Read in byte
            val = ord(self.ser.read(1))
            data.append(val)
            
            # Long frame start, reset checksum
            if bid==0 and val==0x68:
                valid = True
                checksum = 0

            # 2nd byte is the frame length
            if valid and bid==1:
                length = val
                bid_end = length+4+2-1
                bid_checksum = bid_end-1

            if valid and bid==2 and val!=length: valid = False                       # 3rd byte is also length, check that its the same as 2nd byte
            if valid and bid==3 and val!=0x68: valid = False                         # 4th byte is the start byte again
            if valid and bid>3 and bid<bid_checksum: checksum += val                 # Increment checksum during data portion of frame        

            if valid and bid==bid_checksum and val!=(checksum % 256): valid = False  # Validate checksum
            if valid and bid==bid_end and val==0x16:                                 # Parse frame if still valid
              return self.parse_frame(data)
              bid = 0
              break

            bid+=1

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
                c.units = []
                c.nodeid = self._settings['nodename']
             
                pages = self._settings['pages']
                pindex = 0
                
                if len(pages)>1:
                    page = pages[pindex]
                    self._log.debug("Set page: "+str(page))
                    self.set_page(self._settings['address'],page)

                for p in range(len(pages)):
                    result = self.request_data(self._settings['address'])
                    if result==None:
                        time.sleep(0.2)
                        result = self.request_data(self._settings['address'])
                    
                    if result!=None:
                        self._log.debug("Decoded MBUS data: "+json.dumps(result))
                        
                        for key in result: 
                            c.names.append(key)
                            c.realdata.append(result[key][0])
                            c.units.append(result[key][1])
                    else:
                        self._log.debug("Decoded MBUS data: None")
                    
                    if len(pages)>1:
                        pindex += 1
                        if pindex>=len(pages):
                            pindex -= len(pages)
                        page = pages[pindex]
                        self._log.debug("Set page: "+str(page))
                        self.set_page(self._settings['address'],page)
                    
                if len(c.realdata)>0:
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
            elif key == 'address':
                self._log.info("Setting %s address: %s", self.name, setting)
                self._settings[key] = int(setting)
                continue
            elif key == 'pages':
                if type(setting)==list:
                    setting = list(map(int, setting))
                else:
                    setting = [int(setting)]
                self._log.info("Setting %s pages: %s", self.name, json.dumps(setting))
                self._settings[key] = setting
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
