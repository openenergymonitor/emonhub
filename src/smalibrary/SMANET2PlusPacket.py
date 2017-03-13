# GNU GENERAL PUBLIC LICENSE -  Version 2, June 1991
# See LICENCE and README file for details

import array
import math

__author__ = 'Stuart Pittaway'

class SMANET2PlusPacket:
    """Holds a second type of SMA protocol packet"""

    def __init__(self, ctrl1=0, ctrl2=0, packetcount=0, InverterCodeArray=bytearray(), a=0, b=0, c=0):

        self.packet = bytearray()
        self.FCSChecksum = 0xffff

        self.fcstab = array.array("i", [
            0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf, 0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c,
            0xdbe5, 0xe97e, 0xf8f7, 0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e, 0x9cc9, 0x8d40,
            0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
            0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd, 0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e,
            0xfae7, 0xc87c, 0xd9f5, 0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c, 0xbdcb, 0xac42,
            0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
            0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb, 0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868,
            0x99e1, 0xab7a, 0xbaf3, 0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a, 0xdecd, 0xcf44,
            0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
            0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9, 0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a,
            0xb8e3, 0x8a78, 0x9bf1, 0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738, 0xffcf, 0xee46,
            0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
            0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7, 0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64,
            0x5fed, 0x6d76, 0x7cff, 0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036, 0x18c1, 0x0948,
            0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
            0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5, 0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66,
            0x7eef, 0x4c74, 0x5dfd, 0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134, 0x39c3, 0x284a,
            0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
            0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3, 0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60,
            0x1de9, 0x2f72, 0x3efb, 0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232, 0x5ac5, 0x4b4c,
            0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
            0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1, 0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62,
            0x3ceb, 0x0e70, 0x1ff9, 0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330, 0x7bc7, 0x6a4e,
            0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78
        ])

        if (ctrl1 != 0 or ctrl2 != 0):
            self.pushRawByteArray(bytearray([
                0xff, 0x03
                , 0x60, 0x65
                , ctrl1, ctrl2]));
            self.pushRawByteArray(bytearray([0xff, 0xff, 0xff, 0xff, 0xff, 0xff]))
            self.pushRawByteArray(bytearray([a, b]));
            self.pushRawByteArray(InverterCodeArray);
            self.pushRawByteArray(bytearray([0x00, c, 0x00, 0x00, 0x00, 0x00, packetcount]))

    def getFourByteLong(self, offset):
        value = self.packet[offset] * math.pow(256, 0)
        value += self.packet[offset + 1] * math.pow(256, 1)
        value += self.packet[offset + 2] * math.pow(256, 2)
        value += self.packet[offset + 3] * math.pow(256, 3)
        return long(value);

    def getTwoByteLong(self, offset):
        value = self.packet[offset] * math.pow(256, 0)
        value += self.packet[offset + 1] * math.pow(256, 1)
        return long(value);

    def getThreeByteDouble(self, offset):
        # check if all FFs which is a null value
        if self.packet[offset + 0] == 0xff and self.packet[offset + 1] == 0xff and self.packet[offset + 2] == 0xff:
            return None
        else:
            return self.packet[offset + 0] * math.pow(256, 0) + self.packet[offset + 1] * math.pow(256, 1) + \
                   self.packet[offset + 2] * math.pow(256, 2)

    def getFourByteDouble(self, offset):
        # check if all FFs which is a null value
        if self.packet[offset + 0] == 0xff and self.packet[offset + 1] == 0xff and self.packet[offset + 2] == 0xff and self.packet[offset + 3] == 0xff:
            return None
        else:
            return self.packet[offset + 0] * math.pow(256, 0) + self.packet[offset + 1] * math.pow(256, 1) + \
                   self.packet[offset + 2] * math.pow(256, 2) + self.packet[offset + 3] * math.pow(256,3)

    def get8ByteFloat(self, offset):
        value = self.packet[offset] * math.pow(256, 0)
        value += self.packet[offset + 1] * math.pow(256, 1)
        value += self.packet[offset + 2] * math.pow(256, 2)
        value += self.packet[offset + 3] * math.pow(256, 3)
        value += self.packet[offset + 4] * math.pow(256, 4)
        value += self.packet[offset + 5] * math.pow(256, 5)
        value += self.packet[offset + 6] * math.pow(256, 6)
        value += self.packet[offset + 7] * math.pow(256, 7)
        return value

    def getArray(self):
        return self.packet

    def getPacketCounter(self):
        return self.packet[26]

    def getDestinationAddress(self):
        return self.packet[14:20]

    def totalPayloadLength(self):
        return len(self.packet)

    def totalCalculatedPacketLength(self):
        return self.packet[4] * 4 + 8

    def isPacketFull(self):
        return (4 + self.totalPayloadLength()) == self.totalCalculatedPacketLength()

    def validateChecksum(self, checksum):
        myfcs = self.FCSChecksum ^ 0xffff
        return checksum == myfcs

    def getFragment(self):
        return self.packet[24]

    def getTwoByteuShort(self, offset):
        value = self.packet[offset] * math.pow(256, 0) + self.packet[offset + 1] * math.pow(256, 1)
        return value

    def errorCode(self):
        return self.getTwoByteuShort(22)

    def calculateFCS(self):
        myfcs = 0xffff
        for bte in packet:
            myfcs = (myfcs >> 8) ^ self.fcstab[(myfcs ^ bte) & 0xff]

        myfcs ^= 0xffff
        # print "CalculateFCS={0:04x}".format(myfcs)

    def pushRawByteArray(self, barray):
        for bte in barray: self.pushRawByte(bte)

    def pushRawByte(self, value):
        self.FCSChecksum = (self.FCSChecksum >> 8) ^ self.fcstab[(self.FCSChecksum ^ value) & 0xff]
        self.packet.append(value)

    def getBytesForSending(self):
        outputpacket = bytearray()

        realLength = 0
        # //Header byte
        outputpacket.append(0x7e)
        realLength += 1

        # //Copy packet to output escaping values along the way
        for value in self.packet:
            if (value == 0x7d) or (value == 0x7e) or (value == 0x11) or (value == 0x12) or (value == 0x13):
                outputpacket.append(0x7d)  # //byte to indicate escape character
                outputpacket.append(value ^ 0x20)
                realLength += 1
            else:
                outputpacket.append(value)
                realLength += 1

        self.FCSChecksum ^= 0xffff  # complement

        # Checksum
        outputpacket.append(self.FCSChecksum & 0x00ff)
        realLength += 1
        outputpacket.append((self.FCSChecksum >> 8) & 0x00ff)
        realLength += 1

        # Trailer byte
        outputpacket.append(0x7e)
        realLength += 1

        # print "Packet length {0} vs {1}".format(realLength,self.totalCalculatedPacketLength())

        if (self.totalCalculatedPacketLength() != realLength):
            raise Exception(
                "Packet length is incorrect {0} vs {1}".format(realLength, self.totalCalculatedPacketLength()))

        return outputpacket

    def debugViewPacket(self):
        pos = 0;

        print "L2  ARRAY LENGTH = {0}".format(len(self.packet))
        print "L2 {0:04x}  START = {1:02x}".format(pos, 0x7e)
        pos += 0
        print "L2 {0:04x}  Header= {1:02x} {2:02x} {3:02x} {4:02x}".format(pos, self.packet[pos + 0],
                                                                    self.packet[pos + 1], self.packet[pos + 2],
                                                                    self.packet[pos + 3])
        pos += 4
        print "L2 {0:04x}  Length= {1:02x}  ={2} bytes".format(pos, self.packet[pos], (self.packet[pos] * 4) + 8)
        pos += 1
        print "L2 {0:04x}       ?= {1:02x}".format(pos, self.packet[pos])
        pos += 1
        print "L2 {0:04x}    Add1= {1:02x} {2:02x} {3:02x} {4:02x} {5:02x} {6:02x}".format(pos, self.packet[pos + 0],
                                                                                    self.packet[pos + 1],
                                                                                    self.packet[pos + 2],
                                                                                    self.packet[pos + 3],
                                                                                    self.packet[pos + 4],
                                                                                    self.packet[pos + 5])
        pos += 6
        print "L2 {0:04x}  ArchCd= {1:02x}".format(pos, self.packet[pos])
        pos += 1
        print "L2 {0:04x}    zero= {1:02x}".format(pos, self.packet[pos])
        pos += 1
        print "L2 {0:04x}    Add2= {1:02x} {2:02x} {3:02x} {4:02x} {5:02x} {6:02x}".format(pos, self.packet[pos + 0],
                                                                                    self.packet[pos + 1],
                                                                                    self.packet[pos + 2],
                                                                                    self.packet[pos + 3],
                                                                                    self.packet[pos + 4],
                                                                                    self.packet[pos + 5])
        pos += 6
        print "L2 {0:04x}    zero= {1:02x} {2:02x}".format(pos, self.packet[pos + 0], self.packet[pos + 1])
        pos += 2
        print "L2 {0:04x}   ERROR= {1:02x} {2:02x}".format(pos, self.packet[pos + 0], self.packet[pos + 1])
        pos += 2
        print "L2 {0:04x} Fragmnt= {1:02x}".format(pos, self.packet[pos])
        pos += 1
        print "L2 {0:04x}       ?= {1:02x}".format(pos, self.packet[pos])
        pos += 1
        print "L2 {0:04x} Counter= {1:02x}".format(pos, self.packet[pos])
        pos += 1

        s = ""
        for j in range(pos, len(self.packet)):
            if (j % 16 == 0 or j == pos):
                s += "\n    %08x: " % j

            s += "%02x " % self.packet[j]

        print "L2 Payload= %s" % s
        myfcs = self.FCSChecksum ^ 0xffff
        print "L2 Checksu= {0:02x} {1:02x}".format(myfcs & 0x00ff, (myfcs >> 8) & 0x00ff)
        print "L2    END = {0:02x}".format(0x7e)
