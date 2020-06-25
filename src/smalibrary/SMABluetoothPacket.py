# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

__author__ = 'Stuart Pittaway'

class SMABluetoothPacket:
    def __str__(self):
        return "I am an instance of SMABluetoothPacket"

    def getLevel2Checksum(self):
        return (self.UnescapedArray[-2] << 8) + self.UnescapedArray[-3]

    def lastByte(self):
        return self.UnescapedArray[-1]

    def getLevel2Payload(self):
        skipendbytes = 0
        startbyte = 0

        if self.UnescapedArray[0] == 0x7e:
            startbyte = 1

        if self.lastByte() == 0x7e:
            skipendbytes = 3

        # FIXME This comment says to skip the first 3 bytes, but the code skips the *last* 3 bytes
        # Skip the first 3 bytes, they are the command code 0x0001 and 0x7E start byte
        return self.UnescapedArray[startbyte:-skipendbytes]

    def pushRawByteArray(self, barray):
        # Raw byte array
        for bte in barray:
            self.pushRawByte(bte)

    def pushRawByte(self, value):
        # Accept a byte of ESCAPED data (ie. raw byte from Bluetooth)
        self.UnescapedArray.append(value)
        self.RawByteArray.append(value)

    def pushUnescapedByteArray(self, barray):
        for bte in barray:
            self.pushUnescapedByte(bte)

    def pushUnescapedByte(self, value):
        # Store the raw byte
        self.UnescapedArray.append(value)

        if value == 0x7d or value == 0x7e or value == 0x11 or value == 0x12 or value == 0x13:
            self.RawByteArray.append(0x7d)  # byte to indicate escape character
            self.RawByteArray.append(value ^ 0x20)
        else:
            self.RawByteArray.append(value)

    def setChecksum(self):
        self.header[3] = self.header[0] ^ self.header[1] ^ self.header[2]

    def finish(self):
        # Not seen any packets over 256 bytes, so zero second byte (needs to be fixed LOL!)
        self.header[1] = len(self.RawByteArray) + self.headerlength
        self.header[2] = 0
        self.setChecksum()

        # Just in case!
        if not self.ValidateHeaderChecksum():
            raise Exception("Invalid header checksum when finishing!")

    def pushEscapedByte(self, value):
        previousUnescapedByte = 0

        if len(self.RawByteArray) > 0:
            previousUnescapedByte = self.RawByteArray[-1]

        # Store the raw byte as it was received into RawByteArray
        self.RawByteArray.append(value)

        # did we receive the escape char in previous byte?
        if len(self.RawByteArray) > 0 and previousUnescapedByte == 0x7d:
            self.UnescapedArray[-1] = value ^ 0x20
        else:
            # Unescaped array is same as raw array
            self.UnescapedArray.append(value)

    def sendPacket(self, btSocket):
        return btSocket.send(bytes(self.header + self.SourceAddress + self.DestinationAddress + self.cmdcode + self.RawByteArray))

    def containsLevel2Packet(self):
        return (len(self.UnescapedArray) >= 5 and
                self.UnescapedArray[0] == 0x7e and
                self.UnescapedArray[1] == 0xff and
                self.UnescapedArray[2] == 0x03 and
                self.UnescapedArray[3] == 0x60 and
                self.UnescapedArray[4] == 0x65)

    def CommandCode(self):
        return self.cmdcode[0] + (self.cmdcode[1] << 8)

    def setCommandCode(self, byteone, bytetwo):
        self.cmdcode = bytearray()
        self.cmdcode.append(byteone)
        self.cmdcode.append(bytetwo)

    def getByte(self, indexfromstartofdatapayload):
        return self.UnescapedArray[indexfromstartofdatapayload]

    def pushEscapedByteArray(self, barray):
        for bte in barray:
            self.pushEscapedByte(bte)

    def TotalUnescapedPacketLength(self):
        return len(self.UnescapedArray) + self.headerlength

    def TotalRawPacketLength(self):
        return self.header[1] + (self.header[2] << 8)

    def TotalPayloadLength(self):
        return self.TotalRawPacketLength() - self.headerlength

    def ValidateHeaderChecksum(self):
        # Thanks to
        # http://groups.google.com/group/sma-bluetooth/browse_thread/thread/50fe13a7c39bdce0/2caea56cdfb3a68a#2caea56cdfb3a68a
        # for this checksum information !!
        return (self.header[0] ^ self.header[1] ^ self.header[2] ^ self.header[3]) == 0

    def __init__(self, length1, length2, checksum=0, cmd1=0, cmd2=0, SourceAddress=bytearray(), DestinationAddress=bytearray([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])):
        self.headerlength = 18
        self.SourceAddress = SourceAddress
        self.DestinationAddress = DestinationAddress
        self.header = bytearray([0x7e, length1, length2, checksum])

        # Create our array to hold the payload bytes
        self.RawByteArray = bytearray()
        self.UnescapedArray = bytearray()
        self.setCommandCode(cmd1, cmd2)

        if checksum > 0 and not self.ValidateHeaderChecksum():
            raise Exception("Invalid header checksum!")
