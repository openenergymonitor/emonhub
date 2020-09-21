# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

from collections import namedtuple
import time
from datetime import datetime
from smalibrary.SMABluetoothPacket import SMABluetoothPacket
from smalibrary.SMANET2PlusPacket import SMANET2PlusPacket

__author__ = 'Stuart Pittaway'

# Background Reading
# https://groups.google.com/forum/#!topic/sma-bluetooth/UP4Tp8Ob3OA
# https://github.com/Rincewind76/SMAInverter/blob/master/76_SMAInverter.pm
# https://sbfspot.codeplex.com/ (credit back to myself!!)

def Read_Int_From_BT(btSocket):
    return int.from_bytes(btSocket.recv(1), "big")


def Read_Level1_Packet_From_BT_Stream(btSocket, mylocalBTAddress):
    while True:
        start = Read_Int_From_BT(btSocket)

        while start != 0x7e:
            start = Read_Int_From_BT(btSocket)

        length1 = Read_Int_From_BT(btSocket)
        length2 = Read_Int_From_BT(btSocket)
        checksum = Read_Int_From_BT(btSocket)
        SrcAdd = bytearray(btSocket.recv(6))
        DestAdd = bytearray(btSocket.recv(6))

        packet = SMABluetoothPacket(length1, length2, checksum, Read_Int_From_BT(btSocket), Read_Int_From_BT(btSocket), SrcAdd, DestAdd)

        # Read the whole byte stream unaltered (this contains ESCAPED characters)
        b = bytearray(btSocket.recv(packet.TotalPayloadLength()))

        # Populate the SMABluetoothPacket object with the bytes
        packet.pushEscapedByteArray(b)

        # Tidy up the packet lengths
        packet.finish()

        if DestAdd == mylocalBTAddress and packet.ValidateHeaderChecksum():
            break

    return packet

def read_SMA_BT_Packet(btSocket, waitPacketNumber=0, waitForPacket=False, mylocalBTAddress=bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])):
    bluetoothbuffer = Read_Level1_Packet_From_BT_Stream(btSocket, mylocalBTAddress)

    v = namedtuple("SMAPacket", ["levelone", "leveltwo"])
    v.levelone = bluetoothbuffer  # FIXME that's not how namedtuples work!

    if bluetoothbuffer.containsLevel2Packet():
        # Instance to hold level 2 packet
        level2Packet = SMANET2PlusPacket()

        # Write the payload into a level2 class structure
        level2Packet.pushByteArray(bluetoothbuffer.getLevel2Payload())

        if waitForPacket and level2Packet.getPacketCounter() != waitPacketNumber:
            raise Exception("Wrong Level 2 packet returned!")

        # Loop until we have the entire packet rebuilt (may take several level 1 packets)
        while bluetoothbuffer.CommandCode() != 0x0001 and bluetoothbuffer.lastByte() != 0x7e:
            bluetoothbuffer = Read_Level1_Packet_From_BT_Stream(btSocket, mylocalBTAddress)
            level2Packet.pushByteArray(bluetoothbuffer.getLevel2Payload())
            v.levelone = bluetoothbuffer

        if not level2Packet.isPacketFull():
            raise Exception("Failed to grab all the bytes needed for a Level 2 packet")

        if not level2Packet.validateChecksum(bluetoothbuffer.getLevel2Checksum()):
            raise Exception("Invalid checksum on Level 2 packet")

        v.leveltwo = level2Packet
    return v

def BTAddressToByteArray(hexStr, sep=':'):
    """Convert a hex string containing separators to a bytearray object"""
    return bytearray([int(i, 16) for i in hexStr.split(sep)])

def encodeInverterPassword(InverterPassword):
    """Encodes InverterPassword (digit number) into array for passing to SMA protocol"""
    if len(InverterPassword) > 12:
        raise Exception("Password can only be up to 12 digits in length")

    a = bytearray(InverterPassword, encoding='utf8')
    for i in range(12 - len(a)):
        a.append(0)

    for i in range(len(a)):
        if a[i] == 0:
            a[i] = 0x88
        else:
            a[i] = (a[i] + 0x88) % 0xff

    return a

def getInverterDetails(btSocket, packet_send_counter, mylocalBTAddress, MySerialNumber):
    DeviceClass = {
        '8000': 'AllDevices',
        '8001': 'SolarInverter',
        '8002': 'WindTurbineInverter',
        '8007': 'BatteryInverter',
        '8033': 'Consumer',
        '8064': 'SensorSystem',
        '8065': 'ElectricityMeter',
        '8128': 'CommunicationProduct',
        }

    DeviceType = {
        '359':  'SB 5000TL-20',
        '9073': 'SB 3000HF-30',
        '9074': 'SB 3000TL-21',
        '9075': 'SB 4000TL-21',
        '9076': 'SB 5000TL-21',
        '9119': 'Sunny HomeManager',
        }

    data = request_data(btSocket, packet_send_counter, mylocalBTAddress, MySerialNumber, 0x58000200, 0x00821E00, 0x008220FF)

    reply = {
        "susyid": data.getDestinationSusyid(),
        "serialNumber": data.getDestinationSerial(),
    }

    offset = 40

    valuetype = data.getTwoByte(offset + 1)
    if valuetype == 0x821e:
        reply["inverterName"] = data.getArray()[48:62].decode("utf-8")
        offset += 40

    valuetype = data.getTwoByte(offset + 1)

    #INV_CLASS
    if valuetype == 0x821F:
        idx = 8
        while idx < 40:
            attribute = data.getFourByteLong(offset + idx) & 0x00FFFFFF
            status = data.getByte(offset + idx + 3)

            if attribute == 0xFFFFFE:
                break

            if status == 1:
                reply["Class"] = attribute & 0x0000FFFF
                if str(attribute & 0x0000FFFF) in DeviceClass:
                    reply["ClassName"] = DeviceClass[str(attribute & 0x0000FFFF)]
                else:
                    reply["ClassName"] = "Unknown"
                break

            idx += 4

        offset += 40

    #INV_TYPE
    valuetype = data.getTwoByte(offset + 1)
    if valuetype == 0x8220:
        idx = 8
        while idx < 40:
            attribute = data.getFourByteLong(offset + idx) & 0x00FFFFFF
            status = data.getByte(offset + idx + 3)

            if attribute == 0xFFFFFE:
                break

            if status == 1:
                reply["Type"] = attribute & 0x0000FFFF
                if str(attribute & 0x0000FFFF) in DeviceType:
                    reply["TypeName"] = DeviceType[str(attribute & 0x0000FFFF)]
                else:
                    reply["TypeName"] = "Unknown"
                break

            idx += 4

        offset += 40

    return reply

def logon(btSocket, mylocalBTAddress, MySerialNumber, packet_send_counter, InverterPasswordArray):
    # Logon to inverter
    pluspacket1 = SMANET2PlusPacket(0x0e, 0xa0, packet_send_counter, MySerialNumber, 0x00, 0x01, 0x01)
    pluspacket1.pushLong(0xFFFD040C)
    #0x07 = User logon, 0x0a = installer logon
    pluspacket1.pushLong(0x00000007)
    #Timeout = 900sec ?
    pluspacket1.pushLong(0x00000384)

    pluspacket1.pushLong(int(time.mktime(datetime.today().timetuple())))

    pluspacket1.pushLong(0x00000000)
    pluspacket1.pushByteArray(InverterPasswordArray)

    #Broadcast logon to all inverters
    send = SMABluetoothPacket(0x01, 0x01, 0x00, 0x01, 0x00, mylocalBTAddress)
    send.pushRawByteArray(pluspacket1.getBytesForSending())
    send.finish()
    send.sendPacket(btSocket)

    bluetoothbuffer = read_SMA_BT_Packet(btSocket, packet_send_counter, True, mylocalBTAddress)

    checkPacketReply(bluetoothbuffer, 0x0001)
    if bluetoothbuffer.leveltwo.errorCode() > 0:
        raise Exception("Error code returned from inverter - during logon - wrong password?")

def initaliseSMAConnection(btSocket, mylocalBTAddress, MySerialNumber, packet_send_counter):
    # Wait for 1st message from inverter to arrive (should be an 0002 command)

    bluetoothbuffer = read_SMA_BT_Packet(btSocket, mylocalBTAddress)
    checkPacketReply(bluetoothbuffer, 0x0002)

    netid = bluetoothbuffer.levelone.getByte(4)
    inverterAddress = bluetoothbuffer.levelone.SourceAddress

    # Reply to 0x0002 cmd with our data
    send = SMABluetoothPacket(0x1F, 0x00, 0x00, 0x02, 0x00, mylocalBTAddress, inverterAddress)
    send.pushUnescapedByteArray(bytearray([0x00, 0x04, 0x70, 0x00,
                                           netid,
                                           0x00, 0x00, 0x00, 0x00,
                                           0x01, 0x00, 0x00, 0x00]))
    send.finish()
    send.sendPacket(btSocket)

    # Receive 0x000a cmd
    bluetoothbuffer = read_SMA_BT_Packet(btSocket, mylocalBTAddress)
    checkPacketReply(bluetoothbuffer, 0x000a)

    # Receive 0x000c cmd (sometimes this doesn't turn up!)
    bluetoothbuffer = read_SMA_BT_Packet(btSocket, mylocalBTAddress)
    if bluetoothbuffer.levelone.CommandCode() != 0x0005 and bluetoothbuffer.levelone.CommandCode() != 0x000c:
        raise Exception("Expected different command 0x0005 or 0x000c")

    # Receive 0x0005 if we didn't get it above
    if bluetoothbuffer.levelone.CommandCode() != 0x0005:
        bluetoothbuffer = read_SMA_BT_Packet(btSocket, mylocalBTAddress)
        checkPacketReply(bluetoothbuffer, 0x0005)

    # Now the fun begins...

    send = SMABluetoothPacket(0x3f, 0x00, 0x00, 0x01, 0x00, mylocalBTAddress)
    pluspacket1 = SMANET2PlusPacket(0x09, 0xa0, packet_send_counter, MySerialNumber, 0, 0, 0)
    pluspacket1.pushLong(0x00000200)
    pluspacket1.pushLong(0x00000000)
    pluspacket1.pushLong(0x00000000)
    send.pushRawByteArray(pluspacket1.getBytesForSending())
    send.finish()
    send.sendPacket(btSocket)

    bluetoothbuffer = read_SMA_BT_Packet(btSocket, packet_send_counter, True, mylocalBTAddress)
    checkPacketReply(bluetoothbuffer, 0x0001)
    if bluetoothbuffer.leveltwo.errorCode() > 0:
        raise Exception("Error code returned from inverter")

    packet_send_counter += 1

def checkPacketReply(bluetoothbuffer, commandcode):
    if bluetoothbuffer.levelone.CommandCode() != commandcode:
        raise Exception("Expected command 0x{0:04x} received 0x{1:04x}".format(commandcode, bluetoothbuffer.levelone.CommandCode()))

def logoff(btSocket, packet_send_counter, mylocalBTAddress, MySerialNumber):
    p1 = SMABluetoothPacket(0x01, 0x01, 0x00, 0x01, 0x00, mylocalBTAddress)
    data = SMANET2PlusPacket(0x08, 0xA0, packet_send_counter, MySerialNumber, 0x00, 0x03, 0x00)
    data.pushLong(0xFFFD010E)
    data.pushLong(0xFFFFFFFF)
    p1.pushRawByteArray(data.getBytesForSending())
    p1.finish()
    p1.sendPacket(btSocket)

def request_data(btSocket, packet_send_counter, mylocalBTAddress, MySerialNumber, cmd, first, last, susyid=0xFFFF, destinationAddress=0xFFFFFFFF):
    send9 = SMABluetoothPacket(0x01, 0x01, 0x00, 0x01, 0x00, mylocalBTAddress)
    pluspacket9 = SMANET2PlusPacket(0x09, 0xA0, packet_send_counter, MySerialNumber, 0x00, 0x00, 0x00, susyid, destinationAddress)
    pluspacket9.pushLong(cmd)
    pluspacket9.pushLong(first)
    pluspacket9.pushLong(last)
    send9.pushRawByteArray(pluspacket9.getBytesForSending())
    send9.finish()
    send9.sendPacket(btSocket)
    bluetoothbuffer = read_SMA_BT_Packet(btSocket, packet_send_counter, True, mylocalBTAddress)

    if bluetoothbuffer.leveltwo.errorCode() > 0:
        return None  # FIXME raise an Exception like all the other error paths

    leveltwo = bluetoothbuffer.leveltwo

    if susyid != 0xFFFF and leveltwo.getDestinationSusyid() != susyid:
        raise Exception("request_data reply susy id mismatch")

    if destinationAddress != 0xFFFFFFFF and leveltwo.getDestinationSerial() != destinationAddress:
        raise Exception("request_data reply destination address mismatch")

    if leveltwo.errorCode() != 0:
        raise Exception("request_data error in packet")

    #If no errors return packet
    return leveltwo

SpotValue = namedtuple("spotvalue", ["Description", "Scale", "RecSize"])
spotvalues = {
    0x263f: SpotValue("ACTotalPower", 1, 28),
    0x411e: SpotValue("Ph1ACMax", 1, 28),
    0x411f: SpotValue("Ph2ACMax", 1, 28),
    0x4120: SpotValue("Ph3ACMax", 1, 28),
    0x4640: SpotValue("Ph1Power", 1, 28),
    0x4641: SpotValue("Ph2Power", 1, 28),
    0x4642: SpotValue("Ph3Power", 1, 28),
    0x4648: SpotValue("Ph1ACVolt", 100, 28),
    0x4649: SpotValue("Ph2ACVolt", 100, 28),
    0x464a: SpotValue("Ph3ACVolt", 100, 28),
    0x4650: SpotValue("Ph1ACCurrent", 1000, 28),
    0x4651: SpotValue("Ph2ACCurrent", 1000, 28),
    0x4652: SpotValue("Ph3ACCurrent", 1000, 28),
    0x4657: SpotValue("ACGridFreq", 100, 28),

    0x2601: SpotValue("TotalYield", 1, 16),  # 8 byte word
    0x2622: SpotValue("DayYield", 1, 16),  # 8 byte word
    0x462f: SpotValue("FeedInTime", 3600, 16),  # 8 byte word
    0x462e: SpotValue("OperatingTime", 3600, 16),  # 8 byte word

    0x251e: SpotValue("DCPower", 1, 28),
    0x451f: SpotValue("DCVoltage", 100, 28),
    0x4521: SpotValue("DCCurrent", 1000, 28),

    0x2377: SpotValue("InvTemperature", 100, 28),
    0x821e: SpotValue("Inverter Name", 0, 28),
    0x295A: SpotValue("ChargeStatus", 1, 28),
}

SpotValueOutput = namedtuple("SpotValueOutput", ["Label", "Value"])

def extract_data(level2Packet):
    #Return a dictionary
    outputlist = {}

    #Start here
    offset = 40

    while offset < level2Packet.totalPayloadLength():
        classtype = level2Packet.getByte(offset)
        #classtype should always be =1
        readingtype = level2Packet.getTwoByte(offset + 1)
        dataType = level2Packet.getByte(offset + 3)

        if readingtype == 0:
            break

        if dataType != 0x10 and dataType != 0x08:
            # Not TEXT or STATUS, so it should be DWORD
            value = level2Packet.getTwoByte(offset + 8)

            # Check for NULLs
            if value == 0x8000 or value == 0xFFFF:
                value = 0

            if readingtype in spotvalues:
                v = spotvalues[readingtype]

                #Check if its an 4 byte value (QWORD)
                if v.RecSize == 16:
                    value = level2Packet.getEightByte(offset + 8)
                    if value == 0x80000000 or value == 0xFFFFFFFF:
                        value = 0
                # Special case for DC voltage/current input (aka SPOT_UDC1 / SPOT_UDC2, etc)
                if readingtype == 0x451f or readingtype == 0x4521:
                    readingDescription = v.Description + str(classtype)
                    outputlist[readingDescription] = SpotValueOutput(readingDescription, round(float(value) / float(v.Scale), 4))
                else:
                    # normal condition
                    outputlist[v.Description] = SpotValueOutput(v.Description, round(float(value) / float(v.Scale), 4))
                offset += v.RecSize
            else:
                #Output to caller in raw format for debugging
                outputlist[readingtype] = SpotValueOutput("DebugX{0:04x}".format(readingtype), value)

                #Guess offset/default
                offset += 28

    return outputlist
