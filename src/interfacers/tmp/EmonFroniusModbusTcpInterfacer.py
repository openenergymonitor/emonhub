from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from . import EmonModbusTcpInterfacer as EmonModbusTcpInterfacer

"""class EmonModbusTcpInterfacer
Monitors Solar Inverter using modbus tcp
"""

class EmonFroniusModbusTcpInterfacer(EmonModbusTcpInterfacer):

    def __init__(self, name, modbus_IP='192.168.1.10', modbus_port=502):
        """Initialize Interfacer
        com_port (string): path to COM port
        """

        # Initialization
        super().__init__(name)

        # Connection opened by parent class INIT
        # Retrieve Fronius specific inverter info if connection successful
        self._log.debug("Fronius args: " + str(modbus_IP) + " - " + str(modbus_port))
        self._log.debug("EmonFroniusModbusTcpInterfacer: Init")
        if self._modcon:
            # Display device firmware version and current settings
            self.info = ["", ""]
            #self._log.info("Modtcp Connected")
            r2 = self._con.read_holding_registers(40005 - 1, 4, unit=1)
            r3 = self._con.read_holding_registers(40021 - 1, 4, unit=1)
            invBrand = BinaryPayloadDecoder.fromRegisters(r2.registers, endian=Endian.Big)
            invModel = BinaryPayloadDecoder.fromRegisters(r3.registers, endian=Endian.Big)
            self._log.info(self.name +  " Inverter: " + invBrand.decode_string(8) + " " + invModel.decode_string(8))
            swDM = self._con.read_holding_registers(40037 - 1, 8, unit=1)
            swInv = self._con.read_holding_registers(40045 - 1, 8, unit=1)
            swDMdecode = BinaryPayloadDecoder.fromRegisters(swDM.registers, endian=Endian.Big)
            swInvdecode = BinaryPayloadDecoder.fromRegisters(swInv.registers, endian=Endian.Big)
            self._log.info(self.name + " SW Versions: Datamanager " + swDMdecode.decode_string(16) + "- Inverter " + swInvdecode.decode_string(16))
            r1 = self._con.read_holding_registers(40070 - 1, 1, unit=1)
            ssModel = BinaryPayloadDecoder.fromRegisters(r1.registers, endian=Endian.Big)
            self._log.info(self.name + " SunSpec Model: " + str(ssModel.decode_16bit_uint()))
