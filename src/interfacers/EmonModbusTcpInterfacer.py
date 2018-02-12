import time
import Cargo
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
import emonhub_coder
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from emonhub_interfacer import EmonHubInterfacer

"""class EmonModbusTcpInterfacer
Monitors Solar Inverter using modbus tcp
"""

class EmonModbusTcpInterfacer(EmonHubInterfacer):

    def __init__(self, name, modbus_IP='192.168.1.10', modbus_port=0):
        """Initialize Interfacer
        com_port (string): path to COM port
        """

# Initialization
        super(EmonModbusTcpInterfacer, self).__init__(name)

    # open connection
        self._log.debug("EmonModbusTcpInterfacer args: " + str(modbus_IP) + " - " + str(modbus_port) )
        self._con = self._open_modTCP(modbus_IP,modbus_port)
        if self._modcon :
            self._log.info("Modbustcp client Connected")
        else:
            self._log.info("Connection to ModbusTCP client failed. Will try again")


    def set(self, **kwargs):

        for key in kwargs.keys():
            setting = kwargs[key]
            self._settings[key] = setting
            self._log.debug("Setting " + self.name + " %s: %s" % (key, setting) )

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
                self._log.info("Opening modbusTCP connection: " + str(modbus_port) + " @ " +str(modbus_IP))
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
            if "nUnit" in self._settings:
                nUnitList = self._settings["nUnit"]
            else:
                nUnitList = None

            for idx, rName in enumerate(rNameList):
                register = int(registerList[idx])
                qty = int(nRegList[idx])
                rType = rTypeList[idx]
                if nUnitList is not None:
                    unitId = int(nUnitList[idx])
                else:
                    unitId = 1

                self._log.debug("register # :" + str(register) + ", qty #: " + str(qty) + ", unit #: " + str(unitId))

                try:
                    self.rVal = self._con.read_holding_registers(register-1,qty,unit=unitId)
                    assert(self.rVal.function_code < 0x80)
                except Exception as e:
                    self._log.error("Connection failed on read of register: " +str(register) + " : " + str(e))
                    self._modcon = False
                else:
                    #self._log.debug("register value:" + str(self.rVal.registers)+" type= " + str(type(self.rVal.registers)))
                    #f = f + self.rVal.registers
                    decoder = BinaryPayloadDecoder.fromRegisters(self.rVal.registers, endian=Endian.Big)
                    self._log.debug("register type: " + str(rType))

                    if rType == "uint16":
                        rValD = decoder.decode_16bit_uint()
                        t = emonhub_coder.encode('H',rValD)
                        f = f + list(t)
                    elif rType == "uint32":
                        rValD = decoder.decode_32bit_uint()
                        t = emonhub_coder.encode('I',rValD)
                        f = f + list(t)
                    elif rType == "uint64":
                        rValD = decoder.decode_64bit_uint()
                        t = emonhub_coder.encode('Q',rValD)
                        f = f + list(t)
                    elif rType == "int16":
                        rValD = decoder.decode_16bit_int()
                        t = emonhub_coder.encode('h',rValD)
                        f = f + list(t)
                    elif rType == "string":
                        rValD = decoder.decode_string(qty*2)
                        t = rValD
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
