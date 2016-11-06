import time
from pydispatch import dispatcher

import datetime
import Cargo
import logging
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
import emonhub_coder
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
import emonhub_interfacer as ehi

"""class EmonModbusTcpInterfacer
Monitors Solar Inverter using modbus tcp
"""

class EmonModbusTcpInterfacer(ehi.EmonHubInterfacer):

    def __init__(self, name, modbus_IP='192.168.1.10', modbus_port=0):
        """Initialize Interfacer
        com_port (string): path to COM port
        """

# Initialization
        super(EmonModbusTcpInterfacer, self).__init__(name)
#        if modbus_port != 0:
#            super(EmonModbusTcpInterfacer, self).__init__(name, modbus_IP, modbus_port)
#        else:
#            super(EmonModbusTcpInterfacer, self).__init__(name, modbus_IP, 502)

    # open connection
	#self._log.info("args: " + modbus_IP + " - " + modbus_port )
	self._con = self._open_modTCP(modbus_IP,modbus_port)
	if self._modcon :
            # Display device firmware version and current settings
	    self.info =["",""]
            #self._log.info("Modtcp Connected")
            r2= self._con.read_holding_registers(40005-1,4,unit=1)
            r3= self._con.read_holding_registers(40021-1,4,unit=1)
            invBrand = BinaryPayloadDecoder.fromRegisters(r2.registers, endian=Endian.Big)
            invModel = BinaryPayloadDecoder.fromRegisters(r3.registers, endian=Endian.Big)
            self._log.info( self.name +  " Inverter: " + invBrand.decode_string(8) + invModel.decode_string(8))
            swDM= self._con.read_holding_registers(40037-1,8,unit=1)
            swInv= self._con.read_holding_registers(40045-1,8,unit=1)
            swDMdecode = BinaryPayloadDecoder.fromRegisters(swDM.registers, endian=Endian.Big)
            swInvdecode = BinaryPayloadDecoder.fromRegisters(swInv.registers, endian=Endian.Big)
            self._log.info( self.name + " SW Versions: Datamanager " + swDMdecode.decode_string(16) + "- Inverter " + swInvdecode.decode_string(16))
            r1 = self._con.read_holding_registers(40070-1,1,unit=1)
            ssModel = BinaryPayloadDecoder.fromRegisters(r1.registers, endian=Endian.Big)
            self._log.info( self.name + " SunSpec Model: " + str(ssModel.decode_16bit_uint()) )


    def set(self, **kwargs):

        for key in kwargs.keys():
            setting = kwargs[key]
            self._settings[key] = setting
            self._log.info("Setting " + self.name + " %s: %s" % (key, setting) )

    def close(self):
                    
        # Close TCP connection
        if self._con is not None:
            self._log.debug("Closing tcp port")
        self._con.close()

    def _open_modTCP(self,modbus_IP,modbus_port):
        """ Open connection to modbus device """

        try:
            c = ModbusClient(modbus_IP,modbus_port)
	    if c.connect():
                self._log.debug("opening TCP connection: " + str(modbus_port) + " @ " +str(modbus_IP))
		self._modcon = True
	    else:
		self._log.debug("Connection failed")
		self._modcon = False
        except Exception as e:
            self._log.error("modbusTCP connection failed" + str(e))
            #raise EmonHubInterfacerInitError('Could not open connection to host %s' %modbus_IP)
	    pass
        else:
            return c


    def read(self):
        """ Read registers from client"""

	time.sleep(float(self._settings["interval"]))
	f = []
        c = Cargo.new_cargo(rawdata="")
        if not self._modcon :
	   self._con.close()
	   self._log.info("Not connected, retrying connect" + str(self.init_settings))
	   self._con = self._open_modTCP(self.init_settings["modbus_IP"],self.init_settings["modbus_port"])

	if self._modcon :
            #self._log.info(" names " + str(self._settings["rName"]))
	    rNameList = self._settings["rName"]
	    #self._log.info("rNames type: " + str(type(rNameList)))
            registerList = self._settings["register"]
            nRegList = self._settings["nReg"]
            rTypeList = self._settings["rType"]

            for idx, rName in enumerate(rNameList):
                register = int(registerList[idx])
                qty = int(nRegList[idx])
                rType = rTypeList[idx]
	        self._log.debug("register # : " + str(register))

                try:
		    self.rVal = self._con.read_holding_registers(register-1,qty,unit=1)
		except Exception as e:
		    self._log.error("Connection failed on read of register" + str(e))
		    self._modcon = False
		else:
	            #self._log.debug("register value:" + str(self.rVal.registers)+" type= " + str(type(self.rVal.registers)))
                    assert(self.rVal.function_code < 0x80)
	            #f = f + self.rVal.registers
                    decoder = BinaryPayloadDecoder.fromRegisters(self.rVal.registers, endian=Endian.Big)
		    self._log.debug("register type: " + str(rType))

                    if rType == "uint16":
                        rValD = decoder.decode_16bit_uint()
                        t = emonhub_coder.encode('H',rValD)
                        f = f + list(t)
                    elif rType == "int16":
                        rValD = decoder.decode_16bit_int()
                        t = emonhub_coder.encode('h',rValD)
                        f = f + list(t)
                    elif rType == "string":
                        rValD = decoder.decode_string(qty*2)
                    elif rType == "float32":
                        rValD = decoder.decode_32bit_float()*10
                        t = emonhub_coder.encode('f',rValD)
                        f = f + list(t)
		    else:
			self._log.error("Register type not found: "+ str(rType) + " Register:" + str(register))
                    self._log.debug("Encoded value: " + str(t))
           
	    self._log.debug("reporting data: " + str(f)) 
            if int(self._settings['nodeId']):
                c.nodeid = int(self._settings['nodeId'])
                c.realdata = f
            else:
                c.nodeid = int(12)
                c.realdata = f
	    self._log.debug("Return from read data: " + str(c.realdata))	
	 
        return c
