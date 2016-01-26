# EmonHub Configuration

## Latest node decoders

### EmonPi: emonPi_RFM69CW_RF12Demo_DiscreteSampling.ino, v2.1

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

### EmonTx v3, emonTxV3_4_DiscreteSampling.ino, v2.3

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
