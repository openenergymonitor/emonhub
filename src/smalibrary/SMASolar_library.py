# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

from collections import namedtuple
import time
from __builtin__ import long
from SMABluetoothPacket import SMABluetoothPacket
from SMANET2PlusPacket import SMANET2PlusPacket
from datetime import datetime

__author__ = 'Stuart Pittaway'

# Background Reading
# https://groups.google.com/forum/#!topic/sma-bluetooth/UP4Tp8Ob3OA
# https://github.com/Rincewind76/SMAInverter/blob/master/76_SMAInverter.pm
# https://sbfspot.codeplex.com/ (credit back to myself!!)

def Read_Level1_Packet_From_BT_Stream(btSocket,mylocalBTAddress=bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])):
    while True:
        #print "Waiting for SMA level 1 packet from Bluetooth stream"
        start = btSocket.recv(1)

        # Need to add in some timeout stuff here
        while start != '\x7e':
            start = btSocket.recv(1)

        length1 = btSocket.recv(1)
        length2 = btSocket.recv(1)
        checksum = btSocket.recv(1)
        SrcAdd = bytearray(btSocket.recv(6))
        DestAdd = bytearray(btSocket.recv(6))

        packet = SMABluetoothPacket(length1, length2, checksum, btSocket.recv(1), btSocket.recv(1), SrcAdd, DestAdd)

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
    #if waitForPacket:
    #    print "Waiting for reply to packet number {0:02x}".format(waitPacketNumber)
    #else:
    #    print "Waiting for reply to any packet"

    bluetoothbuffer = Read_Level1_Packet_From_BT_Stream(btSocket,mylocalBTAddress)

    v = namedtuple("SMAPacket", ["levelone", "leveltwo"], verbose=False)
    v.levelone = bluetoothbuffer

    if bluetoothbuffer.containsLevel2Packet():
        # Instance to hold level 2 packet
        level2Packet = SMANET2PlusPacket()

        # Write the payload into a level2 class structure
        level2Packet.pushByteArray(bluetoothbuffer.getLevel2Payload())

        if waitForPacket == True and level2Packet.getPacketCounter() != waitPacketNumber:
            #print("Received packet number {0:02x} expected {1:02x}".format(level2Packet.getPacketCounter(),waitPacketNumber))
            raise Exception("Wrong Level 2 packet returned!")

        # if bluetoothbuffer.CommandCode() == 0x0008:
            # print "Level 2 packet length (according to packet): %d" % level2Packet.totalCalculatedPacketLength()

        # Loop until we have the entire packet rebuilt (may take several level 1 packets)
        while (bluetoothbuffer.CommandCode() != 0x0001) and (bluetoothbuffer.lastByte() != 0x7e):
            bluetoothbuffer = Read_Level1_Packet_From_BT_Stream(btSocket,mylocalBTAddress)
            level2Packet.pushByteArray(bluetoothbuffer.getLevel2Payload())
            v.levelone = bluetoothbuffer

        if not level2Packet.isPacketFull():
            raise Exception("Failed to grab all the bytes needed for a Level 2 packet")

        if not level2Packet.validateChecksum(bluetoothbuffer.getLevel2Checksum()):
            raise Exception("Invalid checksum on Level 2 packet")

        v.leveltwo = level2Packet

        # Output the level2 payload (after its been combined from multiple packets if needed)
        #print level2Packet.debugViewPacket()
    return v

def LogMessageWithByteArray(message, ba):
    """Simple output of message and bytearray data in hex for debugging"""
    print("{0}:{1}".format(message.rjust(21), ByteToHex(ba)))


def ByteToHex(byteStr):
    """Convert a byte string to it's hex string representation e.g. for output."""
    return ''.join(["%02X " % x  for x in byteStr])

def BTAddressToByteArray(hexStr, sep):
    """Convert a  hex string containing seperators to a bytearray object"""
    b = bytearray()
    for i in hexStr.split(sep):
        b.append(int(i, 16))
    return b

def encodeInverterPassword(InverterPassword):
    # """Encodes InverterPassword (digit number) into array for passing to SMA protocol"""
    if len(InverterPassword) > 12:
        raise Exception("Password can only be up to 12 digits in length")

    a = bytearray(InverterPassword)

    for i in range( 12- len(a)):
        a.append(0)

    for i in range(len(a)):
        if a[i] == 0:
            a[i] = 0x88
        else:
            a[i] = (a[i] + 0x88) % 0xff

    return a

def floattobytearray(value):
    # Converts an float value into 4 single bytes inside a bytearray
    # useful for converting epoch dates
    b = bytearray()
    hexStr = "{0:08x}".format(long(value))
    b.append(chr(int (hexStr[0:2], 16)))
    b.append(chr(int (hexStr[2:4], 16)))
    b.append(chr(int (hexStr[4:6], 16)))
    b.append(chr(int (hexStr[6:8], 16)))

    b.reverse()
    return b


def getInverterDetails(btSocket, packet_send_counter, mylocalBTAddress, MySerialNumber, AddressFFFFFFFF):

    DeviceClass={}
    DeviceClass['8000']='AllDevices'
    DeviceClass['8001']='SolarInverter'
    DeviceClass['8002']='WindTurbineInverter'
    DeviceClass['8007']='BatteryInverter'
    DeviceClass['8033']='Consumer'
    DeviceClass['8064']='SensorSystem'
    DeviceClass['8065']='ElectricityMeter'
    DeviceClass['8128']='CommunicationProduct'

    DeviceType={}
    DeviceType['9073']='SB 3000HF-30'
    DeviceType['9074']='SB 3000TL-21'
    DeviceType['9075']='SB 4000TL-21'
    DeviceType['9076']='SB 5000TL-21'
    DeviceType['9119']='Sunny HomeManager'

    data=request_data(btSocket, packet_send_counter, mylocalBTAddress, MySerialNumber, AddressFFFFFFFF, 0x58000200, 0x00821E00, 0x008220FF)

    reply = {}

    reply["susyid"] = data.getDestinationSusyid()
    reply["serialNumber"] = data.getDestinationSerial()

    # idate = bluetoothbuffer.leveltwo.getFourByteLong(40 + 4)
    # t = time.localtime(long(idate))

    offset=40

    valuetype = data.getTwoByte(offset + 1)
    if valuetype == 0x821e:
        reply["inverterName"] = data.getArray()[48:62].decode("utf-8")
        offset+=40

    valuetype = data.getTwoByte(offset + 1)

    #INV_CLASS
    if valuetype == 0x821F:
        idx=8
        while idx < 40:
            attribute = data.getFourByteLong(offset + idx) & 0x00FFFFFF
            status = data.getByte(offset + idx + 3)

            if (attribute == 0xFFFFFE):
                break

            if (status == 1):
                reply["Class"]=attribute & 0x0000FFFF
                if str(attribute & 0x0000FFFF) in DeviceClass:
                    reply["ClassName"]=DeviceClass[str(attribute & 0x0000FFFF)]
                else:
                    reply["ClassName"]="Unknown"
                break

            idx+=4

        offset+=40

    #INV_TYPE
    valuetype = data.getTwoByte(offset + 1)
    if valuetype == 0x8220:
        idx=8
        while idx < 40:
            attribute = data.getFourByteLong(offset + idx) & 0x00FFFFFF
            status = data.getByte(offset + idx + 3)

            if (attribute == 0xFFFFFE):
                break

            if (status == 1):
                reply["Type"]=attribute & 0x0000FFFF
                if str(attribute & 0x0000FFFF) in DeviceType:
                    reply["TypeName"]=DeviceType[str(attribute & 0x0000FFFF)]
                else:
                    reply["TypeName"]="Unknown"
                break

            idx+=4

        offset+=40


    return reply

def logon(btSocket,mylocalBTAddress,AddressFFFFFFFF,MySerialNumber,packet_send_counter, InverterPasswordArray):
    # Logon to inverter
    pluspacket1 = SMANET2PlusPacket(0x0e, 0xa0, packet_send_counter, MySerialNumber,  0x00,  0x01, 0x01)
    pluspacket1.pushLong(0xFFFD040c)
    #0x07 = User logon, 0x0a = installer logon
    pluspacket1.pushLong(0x00000007)
    #Timeout = 900sec ?
    pluspacket1.pushLong(0x00000384)
    pluspacket1.pushByteArray( floattobytearray(time.mktime(datetime.today().timetuple())))
    pluspacket1.pushLong(0x00000000)
    pluspacket1.pushByteArray(InverterPasswordArray)
    send = SMABluetoothPacket(0x01, 0x01, 0x00, 0x01, 0x00, mylocalBTAddress, AddressFFFFFFFF)
    send.pushRawByteArray(pluspacket1.getBytesForSending())
    send.finish()
    send.sendPacket(btSocket)

    bluetoothbuffer = read_SMA_BT_Packet(btSocket, packet_send_counter, True, mylocalBTAddress)

    checkPacketReply(bluetoothbuffer, 0x0001)
    if bluetoothbuffer.leveltwo.errorCode() > 0:
        raise Exception("Error code returned from inverter - during logon - wrong password?")



def initaliseSMAConnection(btSocket,mylocalBTAddress,AddressFFFFFFFF,MySerialNumber,packet_send_counter):
    # Wait for 1st message from inverter to arrive (should be an 0002 command)
    bluetoothbuffer = read_SMA_BT_Packet(btSocket,mylocalBTAddress)
    checkPacketReply(bluetoothbuffer,0x0002);

    netid = bluetoothbuffer.levelone.getByte(4);
    #print "netid=%02x" % netid
    inverterAddress = bluetoothbuffer.levelone.SourceAddress;

    # Reply to 0x0002 cmd with our data
    send = SMABluetoothPacket(0x1F, 0x00, 0x00, 0x02, 0x00, mylocalBTAddress, inverterAddress);
    send.pushUnescapedByteArray( bytearray([0x00, 0x04, 0x70, 0x00,
                                netid,
                                0x00, 0x00, 0x00, 0x00,
                                0x01, 0x00, 0x00, 0x00]) )
    send.finish()
    send.sendPacket(btSocket);

    # Receive 0x000a cmd
    bluetoothbuffer = read_SMA_BT_Packet(btSocket,mylocalBTAddress);
    checkPacketReply(bluetoothbuffer,0x000a);

    # Receive 0x000c cmd (sometimes this doesnt turn up!)
    bluetoothbuffer = read_SMA_BT_Packet(btSocket,mylocalBTAddress);
    if bluetoothbuffer.levelone.CommandCode() != 0x0005 and bluetoothbuffer.levelone.CommandCode() != 0x000c:
        raise Exception("Expected different command 0x0005 or 0x000c");

    # Receive 0x0005 if we didnt get it above
    if bluetoothbuffer.levelone.CommandCode() != 0x0005:
        bluetoothbuffer = read_SMA_BT_Packet(btSocket,mylocalBTAddress)
        checkPacketReply(bluetoothbuffer,0x0005)

    # Now the fun begins...

    send = SMABluetoothPacket(0x3f, 0x00, 0x00, 0x01, 0x00, mylocalBTAddress, AddressFFFFFFFF)
    pluspacket1 = SMANET2PlusPacket(0x09, 0xa0, packet_send_counter, MySerialNumber, 0, 0, 0)
    pluspacket1.pushLong(0x00000200)
    pluspacket1.pushLong(0x00000000)
    pluspacket1.pushLong(0x00000000)
    send.pushRawByteArray(pluspacket1.getBytesForSending())
    send.finish()
    send.sendPacket(btSocket)

    bluetoothbuffer = read_SMA_BT_Packet(btSocket, packet_send_counter, True,mylocalBTAddress)
    checkPacketReply(bluetoothbuffer,0x0001)
    if bluetoothbuffer.leveltwo.errorCode() > 0:
        raise Exception("Error code returned from inverter")

    packet_send_counter += 1

    inverterSerial = bluetoothbuffer.leveltwo.getDestinationAddress()

    #This is a logoff command..
    #send = SMABluetoothPacket(0x3B, 0, 0x00, 0x01, 0x00, mylocalBTAddress, AddressFFFFFFFF)
    #pluspacket1 = SMANET2PlusPacket(0x08, 0xA0, packet_send_counter, MySerialNumber, 0x00, 0x03, 0x03)
    #pluspacket1.pushLong(0xFFFD010E)
    #pluspacket1.pushLong(0xFFFFFFFF)
    #send.pushRawByteArray(pluspacket1.getBytesForSending())
    #send.finish()
    #send.sendPacket(btSocket)
    #packet_send_counter += 1

def checkPacketReply(bluetoothbuffer,commandcode):
    if bluetoothbuffer.levelone.CommandCode() != commandcode:
        raise Exception("Expected command 0x{0:04x} received 0x{1:04x}".format(commandcode,bluetoothbuffer.levelone.CommandCode()))

def logoff(btSocket, packet_send_counter, mylocalBTAddress, MySerialNumber, AddressFFFFFFFF):
    p1 = SMABluetoothPacket(0x01, 0x01, 0x00, 0x01, 0x00, mylocalBTAddress, AddressFFFFFFFF)
    data = SMANET2PlusPacket(0x08, 0xA0, packet_send_counter, MySerialNumber, 0x00, 0x03, 0x00)
    data.pushLong(0xFFFD010E)
    data.pushLong(0xFFFFFFFF)
    p1.pushRawByteArray(data.getBytesForSending())
    p1.finish()
    p1.sendPacket(btSocket)
    return

def request_data(btSocket, packet_send_counter, mylocalBTAddress, MySerialNumber, AddressFFFFFFFF, cmd, first, last):
    send9 = SMABluetoothPacket(0x01, 0x01, 0x00, 0x01, 0x00, mylocalBTAddress, AddressFFFFFFFF)
    pluspacket9 = SMANET2PlusPacket(0x09, 0xA0, packet_send_counter, MySerialNumber, 0x00, 0x00, 0x00)
    pluspacket9.pushLong(cmd)
    pluspacket9.pushLong(first)
    pluspacket9.pushLong(last)
    send9.pushRawByteArray(pluspacket9.getBytesForSending())
    send9.finish()
    send9.sendPacket(btSocket)
    bluetoothbuffer = read_SMA_BT_Packet(btSocket, packet_send_counter, True,mylocalBTAddress)

    if bluetoothbuffer.leveltwo.errorCode() > 0:
        return None

    leveltwo=bluetoothbuffer.leveltwo

    if leveltwo.errorCode() == 0:
        return leveltwo

    return None


def extract_data(level2Packet):
    #Return a dictionary
    outputlist = {}

    spotvaluelist = {}

    SpotValue=namedtuple("spotvalue", ["Description", "Scale", "RecSize"])
    spotvaluelist[0x263f] = SpotValue("ACTotalPower", 1, 28)
    spotvaluelist[0x411e] = SpotValue("Ph1ACMax", 1, 28)
    spotvaluelist[0x411f] = SpotValue("Ph2ACMax", 1, 28)
    spotvaluelist[0x4120] = SpotValue("Ph3ACMax", 1, 28)
    spotvaluelist[0x4640] = SpotValue("Ph1Power", 1, 28)
    spotvaluelist[0x4641] = SpotValue("Ph2Power", 1, 28)
    spotvaluelist[0x4642] = SpotValue("Ph3Power", 1, 28)
    spotvaluelist[0x4648] = SpotValue("Ph1ACVolt",100, 28)
    spotvaluelist[0x4649] = SpotValue("Ph2ACVolt",100, 28)
    spotvaluelist[0x464a] = SpotValue("Ph3ACVolt",100, 28)
    spotvaluelist[0x4650] = SpotValue("Ph1ACCurrent",1000, 28)
    spotvaluelist[0x4651] = SpotValue("Ph2ACCurrent",1000, 28)
    spotvaluelist[0x4652] = SpotValue("Ph3ACCurrent",1000, 28)
    spotvaluelist[0x4657] = SpotValue("ACGridFreq",100, 28)

    spotvaluelist[0x2601] = SpotValue("TotalYield",1, 16)   #8 byte word
    spotvaluelist[0x2622] = SpotValue("DayYield",1, 16) #8 byte word
    spotvaluelist[0x462f] = SpotValue("FeedInTime",3600, 16)#8 byte word
    spotvaluelist[0x462e] = SpotValue("OperatingTime",3600, 16)#8 byte word

    spotvaluelist[0x251e] = SpotValue("DCPower1",1, 28)
    spotvaluelist[0x451f] = SpotValue("DCVoltage1",100, 28)
    spotvaluelist[0x4521] = SpotValue("DCCurrent1",1000, 28)

    spotvaluelist[0x2377] = SpotValue("InvTemperature",100, 28)
    #spotvaluelist[0x821e] = SpotValue("Inverter Name",0, 28)
    spotvaluelist[0x295A] = SpotValue("ChargeStatus",1, 28)


    SpotValueOutput=namedtuple("SpotValueOutput", ["Label", "Value"])

    #Start here
    offset = 40

    if (level2Packet.totalPayloadLength()==0):
        return outputlist

    while (offset < level2Packet.totalPayloadLength()):
        recordSize=28
        value=0
        classtype = level2Packet.getByte(offset)
        #classtype should always be =1
        readingtype = level2Packet.getTwoByte(offset+1)
        dataType = level2Packet.getByte(offset+3)
        datetime = level2Packet.getFourByteLong(offset+4)

        if (readingtype==0):
            break;

        if (dataType != 0x10) and (dataType != 0x08):
            # Not TEXT or STATUS, so it should be DWORD
            value = level2Packet.getTwoByte(offset+8)

            #Check for NULLs
            if (value == 0x8000) or (value == 0xFFFF):
                value = 0;

            if readingtype in spotvaluelist:
                v = spotvaluelist[readingtype]

                #Check if its an 4 byte value (QWORD)
                if (v.RecSize==16):
                    value = level2Packet.getEightByte(offset+8)
                    if (value == 0x80000000) or (value == 0xFFFFFFFF):
                        value = 0;


                # Special case for DC voltage input (aka SPOT_UDC1 / SPOT_UDC2)
                #if (readingtype==0x451f):
                #    if (classtype==1):
                #        outputlist["DCVoltage1"] = SpotValueOutput("DCVoltage1".format(readingtype), toVolt(value))
                #    if (classtype==2):
                #        outputlist["DCVoltage2"] = SpotValueOutput("DCVoltage2".format(readingtype), toVolt(value))
                #else:
                #    outputlist[v.Description] = SpotValueOutput(v.Description, float(value) / float(v.Scale))

                outputlist[v.Description] = SpotValueOutput(v.Description, round( float(value) / float(v.Scale) ,4)  )

                offset+=v.RecSize

            else:
                #Output to caller in raw format for debugging
                outputlist[readingtype] = SpotValueOutput("DebugX{0:04x}".format(readingtype), value)

                #Guess offset/default
                offset+=28

    return outputlist
