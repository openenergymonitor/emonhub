import struct
import math

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
<<<<<<< HEAD
    result = struct.unpack(e + b*s, struct.pack(e + datacode, value))
    return result
    
def unitless_realpower(A,B,vcal,ical,phase_shift):

    scaleFactor = 0x4800                                    # scaling for integer transmission of values
    sampleRate = 0.1073                                     # angle between sample pairs (radians @ 50 Hz). Use 0.1288 for 60 Hz systems

    y = math.sin(phase_shift) / math.sin(sampleRate)        # if phase_shift = 0, y = 0
    x = math.cos(phase_shift) - y * math.cos(sampleRate)    # if phase_shift = 1, x = 1

    return ((A * x - B * y) / scaleFactor)*vcal*ical
    
def unitless_vrms(V,vcal):

    scaleFactor = 0x4800                                    # scaling for integer transmission of values
    return (1.0*V/scaleFactor)*vcal
=======
    return struct.unpack(e + b*s, struct.pack(e + datacode, value))
>>>>>>> origin/master
