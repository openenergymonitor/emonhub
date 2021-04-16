import struct

# Initialize nodes data
# FIXME this shouldn't live here
nodelist = {}


def check_datacode(datacode):
    # Ensure little-endian & standard sizes used
    e = '<'
    try:
        return struct.calcsize(e + datacode)
    except struct.error:
        return False


def decode(datacode, frame):
    # Ensure little-endian & standard sizes used
    e = '<'

    # set the base data type to bytes
    b = 'B'

    # get data size from data code
    s = int(check_datacode(datacode))

    result = struct.unpack(e + datacode[0], struct.pack(e + b*s, *frame))
    return result[0]

def encode(datacode, value):
    # Ensure little-endian & standard sizes used
    e = '<'

    # set the base data type to bytes
    b = 'B'

    # get data size from data code
    s = int(check_datacode(datacode))

    #value = 60
    #datacode = "b"
    return struct.unpack(e + b*s, struct.pack(e + datacode, value))
