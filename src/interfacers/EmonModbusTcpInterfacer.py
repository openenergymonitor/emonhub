import time
import Cargo

try:
    from pymodbus.constants import Endian
    from pymodbus.payload import BinaryPayloadDecoder
    from pymodbus.client.sync import ModbusTcpClient as ModbusClient
    pymodbus_found = True
except ImportError:
    pymodbus_found = False

import emonhub_coder as ehc
from emonhub_interfacer import EmonHubInterfacer

"""class EmonModbusTcpInterfacer
Monitors Modbus devices using modbus tcp
At this stage, only read_holding_registers() is implemented in the read() method
if needed, please change the function to read_input_registers()
"""

class EmonModbusTcpInterfacer(EmonHubInterfacer):

    def __init__(self, name, modbus_IP='192.168.1.10', modbus_port=0):
        """Initialize Interfacer
        com_port (string): path to COM port
        """

        # Initialization
        super().__init__(name)

        if not pymodbus_found:
            self._log.error("PYMODBUS NOT PRESENT BUT NEEDED !!")
        # open connection
        if pymodbus_found:
            self._log.info("pymodbus installed")
            self._log.debug("EmonModbusTcpInterfacer args: " + str(modbus_IP) + " - " + str(modbus_port))
            self._con = self._open_modTCP(modbus_IP, modbus_port)
            if self._modcon:
                 self._log.info("Modbustcp client Connected")
            else:
                 self._log.info("Connection to ModbusTCP client failed. Will try again")

    def set(self, **kwargs):
        for key in kwargs:
            setting = kwargs[key]
            self._settings[key] = setting
            self._log.debug("Setting " + self.name + " %s: %s" % (key, setting))

    def close(self):
        # Close TCP connection
        if self._con is not None:
            self._log.debug("Closing tcp port")
            self._con.close()

    def _open_modTCP(self, modbus_IP, modbus_port):
        """ Open connection to modbus device """

        try:
            c = ModbusClient(modbus_IP, modbus_port)
            if c.connect():
                self._log.info("Opening modbusTCP connection: " + str(modbus_port) + " @ " + str(modbus_IP))
                self._modcon = True
            else:
                self._log.debug("Connection failed")
                self._modcon = False
        except Exception as e:
            self._log.error("modbusTCP connection failed" + str(e))
            #raise EmonHubInterfacerInitError('Could not open connection to host %s' %modbus_IP)
        else:
            return c

    def read(self):
        """ Read registers from client"""
        if pymodbus_found:
            time.sleep(float(self._settings["interval"]))
            f = []
            c = Cargo.new_cargo(rawdata="")
            # valid datacodes list and number of registers associated
            # in modbus protocol, one register is 16 bits or 2 bytes
            valid_datacodes = ({'h': 1, 'H': 1, 'i': 2, 'l': 2, 'I': 2, 'L': 2, 'f': 2, 'q': 4, 'Q': 4, 'd': 4})

            if not self._modcon:
                self._con.close()
                self._log.info("Not connected, retrying connect" + str(self.init_settings))
                self._con = self._open_modTCP(self.init_settings["modbus_IP"], self.init_settings["modbus_port"])

            if self._modcon:
                # fetch nodeid
                if 'nodeId' in self._settings:
                    node = str(self._settings["nodeId"])
                else:
                    self._log.error("please provide a nodeId")
                    return

                # stores registers
                if 'register' in self._settings:
                    registers = self._settings["register"]
                else:
                    self._log.error("please provide a register number or a list of registers")
                    return

                # fetch unitids if present
                UnitIds = self._settings.get("nUnit", None)

                # stores names
                # fetch datacode or datacodes
                if node in ehc.nodelist and 'rx' in ehc.nodelist[node]:
                    rNames = ehc.nodelist[node]['rx']['names']
                    if 'datacode' in ehc.nodelist[node]['rx']:
                        datacode = ehc.nodelist[node]['rx']['datacode']
                        datacodes = None
                    elif 'datacodes' in ehc.nodelist[node]['rx']:
                        datacodes = ehc.nodelist[node]['rx']['datacodes']
                    else:
                        self._log.error("please provide a datacode or a list of datacodes")
                        return

                # check if number of registers and number of names are the same
                if len(rNames) != len(registers):
                    self._log.error("You have to define an equal number of registers and of names")
                    return
                # check if number of names and number of datacodes are the same
                if datacodes is not None:
                    if len(datacodes) != len(rNames):
                        self._log.error("You are using datacodes. You have to define an equal number of datacodes and of names")
                        return

                # calculate expected size in bytes and search for invalid datacode(s)
                expectedSize = 0
                if datacodes is not None:
                    for code in datacodes:
                        if code not in valid_datacodes:
                            self._log.debug("-" * 46)
                            self._log.debug("invalid datacode")
                            self._log.debug("-" * 46)
                            return
                        else:
                            expectedSize += valid_datacodes[code] * 2
                else:
                    if datacode not in valid_datacodes:
                        self._log.debug("-" * 46)
                        self._log.debug("invalid datacode")
                        self._log.debug("-" * 46)
                        return
                    else:
                        expectedSize = len(rNames) * valid_datacodes[datacode] * 2

                self._log.debug("expected bytes number after encoding: " + str(expectedSize))

                # at this stage, we don't have any invalid datacode(s)
                # so we can loop and read registers
                for idx, rName in enumerate(rNames):
                    register = int(registers[idx])
                    if UnitIds is not None:
                        unitId = int(UnitIds[idx])
                    else:
                        unitId = 1
                    if datacodes is not None:
                        datacode = datacodes[idx]

                    self._log.debug("datacode " + datacode)
                    qty = valid_datacodes[datacode]
                    self._log.debug("reading register # :" + str(register) + ", qty #: " + str(qty) + ", unit #: " + str(unitId))

                    try:
                        self.rVal = self._con.read_holding_registers(register - 1, qty, unit=unitId)
                        assert self.rVal.function_code < 0x80
                    except Exception as e:
                        self._log.error("Connection failed on read of register: " + str(register) + " : " + str(e))
                        self._modcon = False
                        #missing datas will lead to an incorrect encoding
                        #we have to drop the payload
                        return
                    else:
                        #self._log.debug("register value:" + str(self.rVal.registers) + " type= " + str(type(self.rVal.registers)))
                        #f = f + self.rVal.registers
                        decoder = BinaryPayloadDecoder.fromRegisters(self.rVal.registers, byteorder=Endian.Big, wordorder=Endian.Big)
                        if datacode == 'h':
                            rValD = decoder.decode_16bit_int()
                        elif datacode == 'H':
                            rValD = decoder.decode_16bit_uint()
                        elif datacode == 'i':
                            rValD = decoder.decode_32bit_int()
                        elif datacode == 'l':
                            rValD = decoder.decode_32bit_int()
                        elif datacode == 'I':
                            rValD = decoder.decode_32bit_uint()
                        elif datacode == 'L':
                            rValD = decoder.decode_32bit_uint()
                        elif datacode == 'f':
                            rValD = decoder.decode_32bit_float() * 10
                        elif datacode == 'q':
                            rValD = decoder.decode_64bit_int()
                        elif datacode == 'Q':
                            rValD = decoder.decode_64bit_uint()
                        elif datacode == 'd':
                            rValD = decoder.decode_64bit_float() * 10

                        t = ehc.encode(datacode, rValD)
                        f = f + list(t)
                        self._log.debug("Encoded value: " + str(t))
                        self._log.debug("value: " + str(rValD))

                #test if payload length is OK
                if len(f) == expectedSize:
                    self._log.debug("payload size OK (" + str(len(f)) + ")")
                    self._log.debug("reporting data: " + str(f))
                    c.nodeid = node
                    c.realdata = f
                    self._log.debug("Return from read data: " + str(c.realdata))
                    return c
                else:
                    self._log.error("incorrect payload size :" + str(len(f)) + " expecting " + str(expectedSize))
