import inspect
import struct
import time
import Cargo
import emonhub_coder as ehc
from emonhub_interfacer import EmonHubInterfacer

"""class EmonModbusTcpInterfacer
Monitors Modbus devices using modbus tcp
At this stage, only read_holding_registers() is implemented in the read() method
if needed, please change the function to read_input_registers()
"""

# valid datacodes and number of registers associated
# in modbus protocol, one register is 16 bits or 2 bytes
REGISTER_COUNT = {'h': 1, 'H': 1, 'i': 2, 'l': 2, 'I': 2, 'L': 2, 'f': 2, 'q': 4, 'Q': 4, 'd': 4}

# Modbus limit on the number of registers returned by a single read
MAX_BLOCK_SIZE = 125


def decode_registers(datacode, registers, word_order="big"):
    """Decode a list of 16 bit registers into a value

    Bytes within a register are always big endian (Modbus standard).
    word_order sets which register holds the most significant word:
    "big" = first register, "little" = last register
    """
    registers = list(registers)
    if word_order == "little":
        registers.reverse()
    raw = b"".join(struct.pack(">H", r & 0xFFFF) for r in registers)
    return struct.unpack(">" + datacode, raw)[0]


def plan_blocks(items, max_block_size=1):
    """Group consecutive items into as few register reads as possible

    items: list of (address, count, unit) in configuration order
    Items are merged when they directly follow the previous item in the same unit
    and the block stays within max_block_size registers.
    Returns a list of blocks [address, count, unit, [item indexes]]
    """
    blocks = []
    for idx, (address, count, unit) in enumerate(items):
        if blocks:
            block = blocks[-1]
            if (unit == block[2] and address == block[0] + block[1]
                    and block[1] + count <= max_block_size):
                block[1] += count
                block[3].append(idx)
                continue
        blocks.append([address, count, unit, [idx]])
    return blocks


def _as_list(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class EmonModbusTcpInterfacer(EmonHubInterfacer):

    def __init__(self, name, modbus_IP='192.168.1.10', modbus_port=502):
        """Initialize Interfacer
        modbus_IP (string): IP address of the modbus device
        modbus_port (int): TCP port of the modbus device
        """

        # Initialization
        super().__init__(name)

        self._con = None
        self._modcon = False
        self._unit_keyword = None
        self._next_read = 0

        self._settings.update({
            'interval': 10,
            'word_order': 'big',
            'unit': 1,
            'zero_based': False,
            'max_block_size': 1
        })

        self.pymodbus_found = True
        try:
            try:
                from pymodbus.client import ModbusTcpClient
            except ImportError:
                # pymodbus 2.x
                from pymodbus.client.sync import ModbusTcpClient
            self.ModbusTcpClient = ModbusTcpClient
        except ImportError as err:
            self.pymodbus_found = False
            self._log.error(err)

        if not self.pymodbus_found:
            self._log.error("PYMODBUS NOT PRESENT BUT NEEDED !!")
        # open connection
        else:
            self._log.info("pymodbus installed")
            self._log.debug("EmonModbusTcpInterfacer args: %s - %s", modbus_IP, modbus_port)
            self._open_modTCP(modbus_IP, modbus_port)
            if self._modcon:
                self._log.info("Modbustcp client Connected")
            else:
                self._log.info("Connection to ModbusTCP client failed. Will try again")

    def set(self, **kwargs):
        for key in kwargs:
            setting = kwargs[key]
            if key == 'word_order':
                setting = str(setting).strip().lower()
                if setting not in ('big', 'little'):
                    self._log.error("word_order must be big or little, not %s", setting)
                    continue
            elif key == 'zero_based':
                setting = _as_bool(setting)
            elif key == 'max_block_size':
                try:
                    setting = int(setting)
                except ValueError:
                    self._log.error("max_block_size must be an integer, not %s", setting)
                    continue
                if not 1 <= setting <= MAX_BLOCK_SIZE:
                    self._log.error("max_block_size must be between 1 and %d", MAX_BLOCK_SIZE)
                    continue
            self._settings[key] = setting
            self._log.debug("Setting %s %s: %s", self.name, key, setting)

    def close(self):
        # Close TCP connection
        if self._con is not None:
            self._log.debug("Closing tcp port")
            self._con.close()
            self._con = None
        self._modcon = False

    def _open_modTCP(self, modbus_IP, modbus_port):
        """ Open connection to modbus device """

        self._modcon = False
        try:
            self._con = self.ModbusTcpClient(modbus_IP, port=int(modbus_port))
            # pymodbus has renamed the unit id argument over time: unit, slave, device_id
            self._unit_keyword = self._find_unit_keyword(self._con.read_holding_registers)
            if self._con.connect():
                self._log.info("Opening modbusTCP connection: %s @ %s", modbus_port, modbus_IP)
                self._modcon = True
            else:
                self._log.debug("Connection failed")
        except Exception as e:
            self._log.error("modbusTCP connection failed %s", e)

    @staticmethod
    def _find_unit_keyword(method):
        try:
            parameters = inspect.signature(method).parameters
        except (TypeError, ValueError):
            return "unit"
        for keyword in ("device_id", "slave", "unit"):
            if keyword in parameters:
                return keyword
        return "unit"

    def _read_plan(self):
        """Build the list of values to read from the current settings

        Returns (node, items, datacodes) or None if the configuration is invalid
        """
        if 'nodeId' not in self._settings:
            self._log.error("please provide a nodeId")
            return None
        node = str(self._settings["nodeId"])

        if 'register' not in self._settings:
            self._log.error("please provide a register number or a list of registers")
            return None
        registers = _as_list(self._settings["register"])

        if node not in ehc.nodelist or 'rx' not in ehc.nodelist[node]:
            self._log.error("please provide a [nodes] entry with rx names for node %s", node)
            return None
        rx = ehc.nodelist[node]['rx']
        rNames = _as_list(rx.get('names', []))

        # check if number of registers and number of names are the same
        if len(rNames) != len(registers):
            self._log.error("You have to define an equal number of registers and of names")
            return None

        # fetch datacode or datacodes
        if 'datacodes' in rx:
            datacodes = _as_list(rx['datacodes'])
            # check if number of names and number of datacodes are the same
            if len(datacodes) != len(rNames):
                self._log.error("You are using datacodes. You have to define an equal number of datacodes and of names")
                return None
        elif 'datacode' in rx:
            datacodes = [rx['datacode']] * len(rNames)
        else:
            self._log.error("please provide a datacode or a list of datacodes")
            return None

        for code in datacodes:
            if code not in REGISTER_COUNT:
                self._log.error("invalid datacode %s", code)
                return None

        # unit id: a list with one entry per register, or a single default
        units = self._settings.get("nUnit", None)
        if units is not None:
            units = _as_list(units)
            if len(units) != len(registers):
                self._log.error("You have to define an equal number of nUnit and of registers")
                return None
        else:
            units = [self._settings["unit"]] * len(registers)

        # registers are configured 1-based by default, the modbus request is 0-based
        offset = 0 if self._settings["zero_based"] else 1

        items = []
        try:
            for register, code, unit in zip(registers, datacodes, units):
                items.append((int(str(register), 0) - offset, REGISTER_COUNT[code], int(unit)))
        except ValueError as e:
            self._log.error("invalid register or unit: %s", e)
            return None

        return node, items, datacodes

    def _read_block(self, address, count, unit):
        """Read a block of holding registers, returns the list of registers or None"""
        # According to the Modbus specification, input registers numbered, e.g., 1-16 are
        # transmitted as 0-15. If input registers must be read instead of holding registers,
        # change read_holding_registers to read_input_registers in the following line.
        try:
            rVal = self._con.read_holding_registers(address, count=count, **{self._unit_keyword: unit})
        except Exception as e:
            self._log.error("Connection failed on read of register: %s : %s", address, e)
            self._modcon = False
            return None

        if rVal.isError() or len(getattr(rVal, "registers", [])) < count:
            self._log.error("Error response reading %d register(s) from %s, unit %s: %s", count, address, unit, rVal)
            return None
        return rVal.registers[:count]

    def read(self):
        """ Read registers from client"""
        if not self.pymodbus_found:
            return

        # time in seconds between reads
        now = time.time()
        if now < self._next_read:
            return
        self._next_read = now + float(self._settings["interval"])

        if not self._modcon:
            self.close()
            self._log.info("Not connected, retrying connect %s", self.init_settings)
            self._open_modTCP(self.init_settings["modbus_IP"], self.init_settings.get("modbus_port", 502))
            if not self._modcon:
                return

        plan = self._read_plan()
        if plan is None:
            return
        node, items, datacodes = plan
        word_order = self._settings["word_order"]

        f = []
        for address, count, unit, indexes in plan_blocks(items, self._settings["max_block_size"]):
            self._log.debug("reading register #: %s, qty #: %s, unit #: %s", address, count, unit)
            registers = self._read_block(address, count, unit)
            if registers is None:
                # missing data would shift the position of the following values
                # we have to drop the payload
                return

            pos = 0
            for idx in indexes:
                datacode = datacodes[idx]
                qty = REGISTER_COUNT[datacode]
                rValD = decode_registers(datacode, registers[pos:pos + qty], word_order)
                pos += qty
                # floats are sent with one decimal place, use a scale of 0.1 in the node config
                if datacode in ('f', 'd'):
                    rValD = rValD * 10

                t = ehc.encode(datacode, rValD)
                f = f + list(t)
                self._log.debug("value: %s encoded: %s", rValD, t)

        c = Cargo.new_cargo(rawdata="")
        c.nodeid = node
        c.realdata = f
        self._log.debug("Return from read data: %s", c.realdata)
        return c
