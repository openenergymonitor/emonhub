# EmonHub Configuration

## Node configuration

An un-configured Emonhub will by default assume that RFM12 or RFM69 data packets received are a series of integers, each 2 bytes long. The radio packet format is quite minimal and non-descriptive and so emonhub cant know how to decode the packets from the received data if the packet structure is any different.

Earlier OpenEnergyMonitor nodes always sent a series of integers and so no decoder configuration was needed, more recent revisions now include the sending of pulse counts or watt hours which would overrun the maximum value that can be sent as an integer. The latest EmonPi, EmonTx3 and EmonTH firmware's all send pulse count as long datatypes at the end of their packets taking up 4 bytes.

Its possible to decode any radio packet that is packed as a binary structure with Emonhub. For example if we look at the relevant part of the node decoder for the emontx v3 we can see 11 integers (h) and one unsigned long at the end (L)

    [[8]]
        [[[rx]]]
           datacodes = h,h,h,h,h,h,h,h,h,h,h,L
           
The node decoder could be left as this if we only wanted to decode the packet structure correctly. Alternatively if the packet structure is a series of integers its possible to write:

    [[8]]
        [[[rx]]]
           datacode = h
           
Notice that the name is datacode rather than datacode**s** with an s

## Standard node decoders

The following lists the standard node decoders for recent versions of the EmonPi, EmonTx v3, EmonTH and EmonTxShield. These are currently included in emonhub.conf and provide automatic decoding of node data.

If you upload the firmware yourself to any of these nodes and wish to have the data decoded with names, units and scaled correctly these are the decoders for the standard firmwares. The node decoders are also included at the top of each firmware file for reference.

### EmonPi: emonPi_RFM69CW_RF12Demo_DiscreteSampling.ino, v2.1+

Firmware location: [emonPi_RFM69CW_RF12Demo_DiscreteSampling.ino](https://github.com/openenergymonitor/emonpi/blob/master/Atmega328/emonPi_RFM69CW_RF12Demo_DiscreteSampling/emonPi_RFM69CW_RF12Demo_DiscreteSampling.ino)

Copied here for reference:

    [[5]]
        nodename = emonPi
        firmware = emonPi_RFM69CW_RF12Demo_DiscreteSampling.ino
        hardware = emonpi
        [[[rx]]]
            names = power1,power2,power1_plus_power2,Vrms,T1,T2,T3,T4,T5,T6,pulseCount
            datacodes = h, h, h, h, h, h, h, h, h, h, L
            scales = 1,1,1,0.01,0.1,0.1,0.1,0.1,0.1,0.1,1
            units = W,W,W,V,C,C,C,C,C,C,p

### EmonTx v3, emonTxV3_4_DiscreteSampling.ino, v2.3+

Firmware location: [emonTxV3_4_DiscreteSampling.ino](https://github.com/openenergymonitor/emonTxFirmware/blob/master/emonTxV3/RFM/emonTxV3.4/emonTxV3_4_DiscreteSampling/emonTxV3_4_DiscreteSampling.ino)

Node ID when DIP switch1 is off = 8, node ID when DIP switch1 is on is 7

Copied here for reference:

    [[8]]
        nodename = emonTx_3
        firmware =V2_3_emonTxV3_4_DiscreteSampling
        hardware = emonTx_(NodeID_DIP_Switch1:OFF)
        [[[rx]]]
           names = power1, power2, power3, power4, Vrms, temp1, temp2, temp3, temp4, temp5, temp6, pulse
           datacodes = h,h,h,h,h,h,h,h,h,h,h,L
           scales = 1,1,1,1,0.01,0.1,0.1, 0.1,0.1,0.1,0.1,1 
           units =W,W,W,W,V,C,C,C,C,C,C,p

### EmonTx v3, emonTxV3_4_DiscreteSampling.ino, v1.6+

Can be on either nodeid 10 or 9

    [[10]]
        nodename = emonTx_1
        firmware =V1_6_emonTxV3_4_DiscreteSampling
        hardware = emonTx_(NodeID_DIP_Switch1:OFF)
        [[[rx]]]
           names = power1, power2, power3, power4, Vrms, temp1, temp2, temp3, temp4, temp5, temp6, pulse
           datacode = h
           scales = 1,1,1,1,0.01,0.1,0.1, 0.1,0.1,0.1,0.1,1 #Firmware V1.6
           units =W,W,W,W,V,C,C,C,C,C,C,p
           
### EmonTx v3, emonTxV3_4_DiscreteSampling.ino, <v1.4

    [[10]]
        nodename = emonTx_1
        firmware =V1_6_emonTxV3_4_DiscreteSampling
        hardware = emonTx_(NodeID_DIP_Switch1:OFF)
        [[[rx]]]
           names = power1, power2, power3, power4, Vrms, temp
           datacode = h
           scales = 1,1,1,1,0.01,0.1
           units =W,W,W,W,V,C

### EmonTH, emonTH_DHT22_DS18B20_RFM69CW_Pulse.ino, v2.6+

Firmware location: [emonTH_DHT22_DS18B20_RFM69CW_Pulse.ino](https://github.com/openenergymonitor/emonTH/blob/master/emonTH_DHT22_DS18B20_RFM69CW_Pulse/emonTH_DHT22_DS18B20_RFM69CW_Pulse.ino)

Standard nodeid's: 23, 24, 25 & 26 depending on DIP switch positions:

    [[23]]
        nodename = emonTH_5
        firmware = V2.x_emonTH_DHT22_DS18B20_RFM69CW_Pulse
        hardware = emonTH_(Node_ID_Switch_DIP1:OFF_DIP2:OFF)
        [[[rx]]]
           names = temperature, external temperature, humidity, battery, pulseCount
           datacodes = h,h,h,h,L
           scales = 0.1,0.1,0.1,0.1,1
           units = C,C,%,V,p

### EmonTH, emonTH_DHT22_DS18B20_RFM69CW.ino v1.5 -> v1.6.1

Firmware location: [emonTH_DHT22_DS18B20_RFM69CW.ino](https://github.com/openenergymonitor/emonTH/blob/master/emonTH_DHT22_DS18B20_RFM69CW/emonTH_DHT22_DS18B20_RFM69CW.ino)

Standard nodeid's: 19, 20, 21 & 22 depending on DIP switch positions:

    [[19]]
        nodename = emonTH_1
        firmware = emonTH_DHT22_DS18B20_RFM69CW
        hardware = emonTH_(Node_ID_Switch_DIP1:OFF_DIP2:OFF)
        [[[rx]]]
           names = temperature, external temperature, humidity, battery
           datacode = h
           scales = 0.1,0.1,0.1,0.1
           units = C,C,%,V

### EmonTx Shield

Firmware location: [Shield_CT1234_Voltage.ino](https://github.com/openenergymonitor/emonTxFirmware/blob/master/emonTxShield/Shield_CT1234_Voltage/Shield_CT1234_Voltage.ino)

    [[6]]
        nodename = emonTxShield
        firmware =emonTxShield
        hardware = emonTxShield
        [[[rx]]]
           names = power1, power2, power3, power4, Vrms
           datacode = h
           scales = 1,1,1,1,0.01
           units =W,W,W,W,V