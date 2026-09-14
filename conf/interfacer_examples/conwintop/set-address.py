from pymodbus.client import ModbusSerialClient

# Serial connection configuration
PORT = '/dev/ttyACM0'    # Adjust to match your serial device path
BAUDRATE = 4800          # Default baud rate for CWT sensors

# Modbus register for Slave ID (0x07D0 = 2000 decimal)
SLAVE_ID_REGISTER = 0x07D0

# Target address configuration
CURRENT_SLAVE_ID = 1     # Current address of the sensor (or use 255 for broadcast)[cite: 3]
NEW_SLAVE_ID = 2         # New Slave ID to assign (Valid range: 1 to 254)[cite: 3]

def change_modbus_address(current_id, new_id):
    if not (1 <= new_id <= 254):
        print(f"Error: Target Slave ID {new_id} is out of valid range (1-254).[cite: 3]")
        return

    client = ModbusSerialClient(
        port=PORT,
        baudrate=BAUDRATE,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=1
    )

    if not client.connect():
        print(f"Failed to connect to RS485 adapter on {PORT}")
        return

    try:
        print(f"Changing Slave ID from {current_id} to {new_id} via register 0x{SLAVE_ID_REGISTER:04X}...[cite: 3]")

        # Write Single Register (Function Code 0x06)[cite: 3]
        response = client.write_register(address=SLAVE_ID_REGISTER, value=new_id, slave=current_id)

        if response.isError():
            print(f"Failed to update Slave ID: {response}")
        else:
            print(f"Successfully sent command! Sensor address updated to {new_id}.[cite: 3]")

            # Verify by querying register 0x07D0 using the NEW Slave ID[cite: 3]
            read_resp = client.read_holding_registers(address=SLAVE_ID_REGISTER, count=1, slave=new_id)
            if not read_resp.isError():
                print(f"Verification Readback at new address ({new_id}): Slave ID = {read_resp.registers[0]}")
            else:
                print("Could not verify new address. Ensure sensor power was not interrupted.")

    finally:
        client.close()

if __name__ == "__main__":
    # Change address from 1 to 2
    change_modbus_address(CURRENT_SLAVE_ID, NEW_SLAVE_ID)
