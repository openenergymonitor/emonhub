import time
import Cargo
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

        self._modcon = False

        self.pymodbus_found = True
        try:
            from pymodbus.constants import Endian
            self.Endian = Endian
            from pymodbus.payload import BinaryPayloadDecoder
            self.BinaryPayloadDecoder = BinaryPayloadDecoder
            from pymodbus.client import ModbusTcpClient
            self.ModbusTcpClient = ModbusTcpClient
        except ModuleNotFoundError as err:
            self.pymodbus_found = False
            self._log.error(err)

        if not self.pymodbus_found:
            self._log.error("PYMODBUS NOT PRESENT BUT NEEDED !!")
        # open connection
        else:
            self._log.info("pymodbus installed")
            self._log.debug("EmonModbusTcpInterfacer args: %s - %s", modbus_IP, modbus_port)
            self._con = self._open_modTCP(modbus_IP, modbus_port)
            if self._modcon:
                self._log.info("Modbustcp client Connected")
            else:
                self._log.info("Connection to ModbusTCP client failed. Will try again")

    def set(self, **kwargs):
        for key in kwargs:
            setting = kwargs[key]
            self._settings[key] = setting
            self._log.debug("Setting %s %s: %s", self.name, key, setting)

    def close(self):
        # Close TCP connection
        if self._con is not None:
            self._log.debug("Closing tcp port")
            self._con.close()

    def _open_modTCP(self, modbus_IP, modbus_port):
        """ Open connection to modbus device """

        try:
            c = self.ModbusTcpClient(modbus_IP, modbus_port)
            if c.connect():
                self._log.info("Opening modbusTCP connection: %s @ %s", modbus_port, modbus_IP)
                self._modcon = True
            else:
                self._log.debug("Connection failed")
                self._modcon = False
        except Exception as e:
            self._log.error("modbusTCP connection failed %s", e)
            #raise EmonHubInterfacerInitError('Could not open connection to host %s' %modbus_IP)
        else:
            return c

    def read(self):
        """ Read registers from client"""
        if self.pymodbus_found:
            time.sleep(float(self._settings["interval"]))
            f = []
            c = Cargo.new_cargo(rawdata="")
            # valid datacodes list and number of registers associated
            # in modbus protocol, one register is 16 bits or 2 bytes
            valid_datacodes = ({'h': 1, 'H': 1, 'i': 2, 'l': 2, 'I': 2, 'L': 2, 'f': 2, 'q': 4, 'Q': 4, 'd': 4})

            if not self._modcon:
                self._con.close()
                self._log.info("Not connected, retrying connect %s", self.init_settings)
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

                self._log.debug("expected bytes number after encoding: %s", expectedSize)

                # at this stage, we don't have any invalid datacode(s)
                # so we can loop and read registers
                for idx, rName in enumerate(rNames):
                    register = int(registers[idx], 0)
                    if UnitIds is not None:
                        unitId = int(UnitIds[idx])
                    else:
                        unitId = 1
                    if datacodes is not None:
                        datacode = datacodes[idx]

                    self._log.debug("datacode %s", datacode)
                    qty = valid_datacodes[datacode]
                    self._log.debug("reading register #: %s, qty #: %s, unit #: %s", register, qty, unitId)

                    try:
                        self.rVal = self._con.read_holding_registers(register - 1, qty, unit=unitId)
                        assert self.rVal.function_code < 0x80
                    except Exception as e:
                        self._log.error("Connection failed on read of register: %s : %s", register, e)
                        self._modcon = False
                        #missing datas will lead to an incorrect encoding
                        #we have to drop the payload
                        return
                    else:
                        #self._log.debug("register value: %s type= %s", self.rVal.registers, type(self.rVal.registers))
                        #f = f + self.rVal.registers
                        decoder = self.BinaryPayloadDecoder.fromRegisters(self.rVal.registers, byteorder=self.Endian.Big, wordorder=self.Endian.Big)
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
                        self._log.debug("Encoded value: %s", t)
                        self._log.debug("value: %s", rValD)

                #test if payload length is OK
                if len(f) == expectedSize:
                    self._log.debug("payload size OK (%d)", len(f))
                    self._log.debug("reporting data: %s", f)
                    c.nodeid = node
                    c.realdata = f
                    self._log.debug("Return from read data: %s", c.realdata)
                    return c
                else:
                    self._log.error("incorrect payload size: %d expecting %d", len(f), expectedSize)
