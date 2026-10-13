import sys
from pymodbus.client import ModbusSerialClient

# Serial connection configuration
PORT = '/dev/ttyACM0'  # Adjust to match your serial device path
BAUDRATE = 4800        # Default baud rate for CWT-DTAS sensor
SLAVE_ID = 1           # Default Modbus device address

# Register address for Pipe Cross-Sectional Area (0x0200 = 512 decimal)
AREA_REGISTER = 0x0200


def calculate_area_cm2(width_cm, height_cm=None):
    """Calculates cross-sectional area in cm² for rectangular or circular ducts."""
    if height_cm is not None:
        # Rectangular duct: Width (cm) * Height (cm)
        return int(width_cm * height_cm)
    else:
        # Circular duct: Width represents diameter (cm)
        radius = width_cm / 2.0
        return int(3.14159 * (radius**2))


def set_duct_area(area_cm2):
    # Ensure value fits within 16-bit register limits (0-65535 cm²)
    if not (0 <= area_cm2 <= 65535):
        print(f"Error: Area {area_cm2} cm² is out of valid range (0 to 65535 cm²).")
        return

    client = ModbusSerialClient(
        port=PORT,
        baudrate=BAUDRATE,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=1,
    )

    if not client.connect():
        print(f"Failed to connect to RS485 adapter on {PORT}")
        return

    try:
        print(
            f"Writing area {area_cm2} cm² to register 0x{AREA_REGISTER:04X} (Slave ID {SLAVE_ID})..."
        )

        # Write Single Holding Register (Function Code 06)[cite: 3]
        response = client.write_register(
            address=AREA_REGISTER, value=area_cm2, slave=SLAVE_ID
        )

        if response.isError():
            print(f"Failed to update register: {response}")
        else:
            print("Successfully updated duct cross-sectional area!")

            # Verify by reading back the updated register[cite: 3]
            read_resp = client.read_holding_registers(
                address=AREA_REGISTER, count=1, slave=SLAVE_ID
            )
            if not read_resp.isError():
                print(
                    f"Verification Readback: {read_resp.registers[0]} cm²"
                )

    finally:
        client.close()


if __name__ == '__main__':
    # Example 1: Rectangular Duct (e.g., Width = 30 cm, Height = 20 cm => 600 cm²)
    width_cm = 30
    height_cm = 20
    area = calculate_area_cm2(width_cm, height_cm)

    # Example 2: Circular Duct (Uncomment below if duct is round, where width = diameter)
    # diameter_cm = 30
    # area = calculate_area_cm2(diameter_cm)

    set_duct_area(area)
