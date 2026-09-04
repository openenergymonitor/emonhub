import inspect


POWER_SCALE = 0.01
VOLTAGE_SCALE = 0.01
CURRENT_SCALE = 0.01
POWER_FACTOR_SCALE = 0.01
ENERGY_SCALE = 0.000001

GRID_BLOCKS = ((0, 32), (1000, 8), (1200, 9))


def _decode_unsigned(registers):
    value = 0
    for offset, register in enumerate(registers):
        value |= (register & 0xFFFF) << (16 * offset)
    return value


def _decode_signed(registers):
    value = _decode_unsigned(registers)
    bits = 16 * len(registers)
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


def decode_u16(registers):
    return _decode_unsigned(registers)


def decode_i16(registers):
    return _decode_signed(registers)


def decode_i32(registers):
    return _decode_signed(registers)


def decode_u64(registers):
    return _decode_unsigned(registers)


def decode_text(registers):
    data = bytearray()
    for register in registers:
        data.extend((register & 0xFF, (register >> 8) & 0xFF))
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


def branch_addresses(device, channel):
    if device not in range(4) or channel not in range(1, 11):
        raise ValueError("device must be 0..3 and channel must be 1..10")
    offset = channel - 1
    voltage = 1209 + 30 * device + 3 * offset
    return {
        "energy": 32 + 40 * device + 4 * offset,
        "return_energy": 192 + 40 * device + 4 * offset,
        "power": 1008 + 20 * device + 2 * offset,
        "voltage": voltage,
        "current": voltage + 1,
        "power_factor": voltage + 2,
    }


class EcoMainReadError(Exception):
    pass


def _device_id_keyword(method):
    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return "unit"
    for keyword in ("device_id", "slave", "unit"):
        if keyword in parameters:
            return keyword
    if any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return "unit"
    raise EcoMainReadError("unsupported pymodbus client signature")


class EcoMainReader:
    def __init__(self, client, unit_id=255):
        self._client = client
        self._unit_id = unit_id
        self._device_id_keyword = _device_id_keyword(
            client.read_holding_registers
        )

    def _read(self, address, count):
        try:
            response = self._client.read_holding_registers(
                address,
                count=count,
                **{self._device_id_keyword: self._unit_id},
            )
        except Exception as exc:
            raise EcoMainReadError(
                f"failed to read holding registers {address}:{count}"
            ) from exc
        if response.isError() or len(getattr(response, "registers", [])) != count:
            raise EcoMainReadError(
                f"invalid holding-register response {address}:{count}"
            )
        return response.registers

    def read_grid(self):
        energy, power, electric = (
            self._read(address, count) for address, count in GRID_BLOCKS
        )
        phases = []
        for phase in range(3):
            power_offset = 2 * phase
            electric_offset = 3 * phase
            phases.append(
                {
                    "power": decode_i32(power[power_offset : power_offset + 2])
                    * POWER_SCALE,
                    "voltage": decode_u16(
                        electric[electric_offset : electric_offset + 1]
                    )
                    * VOLTAGE_SCALE,
                    "current": decode_u16(
                        electric[electric_offset + 1 : electric_offset + 2]
                    )
                    * CURRENT_SCALE,
                    "power_factor": decode_i16(
                        electric[electric_offset + 2 : electric_offset + 3]
                    )
                    * POWER_FACTOR_SCALE,
                }
            )
        return {
            "power": decode_i32(power[6:8]) * POWER_SCALE,
            "energy": decode_u64(energy[12:16]) * ENERGY_SCALE,
            "return_energy": decode_u64(energy[28:32]) * ENERGY_SCALE,
            "phases": phases,
        }

    def read_branch_device(self, device):
        branch_addresses(device, 1)
        forward = self._read(32 + 40 * device, 40)
        reverse = self._read(192 + 40 * device, 40)
        power = self._read(1008 + 20 * device, 20)
        electric = self._read(1209 + 30 * device, 30)
        samples = {}
        for channel in range(1, 11):
            energy_offset = 4 * (channel - 1)
            power_offset = 2 * (channel - 1)
            electric_offset = 3 * (channel - 1)
            samples[channel] = {
                "power": decode_i32(power[power_offset : power_offset + 2])
                * POWER_SCALE,
                "energy": decode_u64(forward[energy_offset : energy_offset + 4])
                * ENERGY_SCALE,
                "return_energy": decode_u64(
                    reverse[energy_offset : energy_offset + 4]
                )
                * ENERGY_SCALE,
                "voltage": decode_u16(
                    electric[electric_offset : electric_offset + 1]
                )
                * VOLTAGE_SCALE,
                "current": decode_u16(
                    electric[electric_offset + 1 : electric_offset + 2]
                )
                * CURRENT_SCALE,
                "power_factor": decode_i16(
                    electric[electric_offset + 2 : electric_offset + 3]
                )
                * POWER_FACTOR_SCALE,
            }
        return samples

    def read_device_info(self):
        registers = self._read(3000, 14)
        version_names = (
            "hardware",
            "ecomain_software",
            "ecomain_firmware",
            "ecosub_1_firmware",
            "ecosub_2_firmware",
            "ecosub_3_firmware",
        )
        return {
            "model": decode_text(registers[0:2]),
            "serial": decode_text(registers[2:8]),
            "versions": {
                name: decode_u16(registers[8 + offset : 9 + offset])
                for offset, name in enumerate(version_names)
            },
        }
