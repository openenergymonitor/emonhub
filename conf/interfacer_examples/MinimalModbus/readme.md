## MinimalModbus

The minimalmodbus interfacer supports a number of Modbus-RTU serial connected electricity meters and devices for monitoring the electricity supply of heat pumps, 
EV Chargers Solar etc.
One or more USB to RS485 converter is needed to read from the modbus output of the meter such as: https://www.amazon.co.uk/gp/product/B07SD65BVF. 

Multiple meters of different types can be mixed on the same serial interface provided the serial parameters of all the meters is the same (Baud rate, parity stop bits)

### Supported Meters include
**SDM120**
A single phase bi-directional electricity meter provides MID certified electricity monitoring up to 45A, ideal for monitoring the electricity supply of heat pumps
EV chargers, Solar etc. 
The SDM120 meter comes in a number of different variants, be sure to order the version with a modbus output.

**SDM630**
A single/ three phase bi-directional electricity meter provides MID certified electricity monitoring up to 100A, ideal for monitoring the electricity supply of heat pumps
EV chargers, Solar etc. 
The SDM630 meter comes in a number of different variants, be sure to order the version with a modbus output.

**RI-D175**
A low cost single phase unidirectional (Import only) electricity meter provides MID certified electricity monitoring up to 45A, ideal for monitoring the electricity supply of heat pumps
EV chargers, Solar etc. 
The RI-D175 meter comes in a number of different variants, be sure to order the version with a modbus output.
https://www.rayleigh.com/media/uploads/RI_Data_Sheet_RI-D175_MID_01_12_20.pdf

**SAMSUNG-ASHP-MIB19N**
Direct connection to a Samsung ASHP MIB19N

**read_interval:** Interval between readings in seconds

**type:** Meter Type

## SDM120 only Meters
```
[[SDM120]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 2400
        parity = none
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sdm120
        # prefix = sdm_
        [[[[meters]]]]
            [[[[[sdm120a]]]]]
                address = 1
                type = sdm120
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
            [[[[[sdm120b]]]]]
                address = 2
                type = sdm120
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
                
```
## Single SDM630 Meter

```
[[SDM630]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB1
        baud = 9600
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sdm630
        # prefix = sdm_
        registers = 0,1,2,3,4,5,6,7,8,26,36,37
        names =  V1,V2,V3,I1,I2,I3,P1,P2,P3,TotalPower,Import_kWh,Export_kWh
        precision = 2,2,2,2,2,2,2,2,2,2,2,2
```
## RI-D175 and SDM120 on same interface
```
[[modbusRTU]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 9600
        parity = none
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = rid175
        # prefix = rid_
        [[[[meters]]]]
            [[[[[rid175]]]]]
                address = 1
                type = rid175
                registers = 0,6,8,10,14,16,18
                names = TotalkWh,V,A,Power,KVA,PF,FR
                scales = 0.01,0.1,0.1,0.01,0.01,0.001,0.01
            [[[[[sdm120]]]]]
                address = 2
                type = sdm120
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
```
## Samsung ASHP
```
[[SAMSUNG-ASHP-MIB19N]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 9600
        parity = even
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = samsung-ashp
        # prefix = sdm_
        [[[[meters]]]]
            [[[[[ashp]]]]]
                address = 1
                type = mib19n
                registers = 75,74,72,65,66,68,52,59,58,2,79
                names = dhw_temp,dhw_target,dhw_status,return_temp,flow_temp,flow_target,heating_status,indoor_temp,indoor_target, defrost_status, away_status
                scales = 0.1,0.1,1,0.1,0.1,0.1,1,0.1,0.1,1,1
                precision = 2,2,1,2,2,2,1,2,2,1,1

'''
