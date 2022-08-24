### SDM120-Modbus

The SDM120-Modbus single phase electricity meter provides MID certified electricity monitoring up to 45A, ideal for monitoring the electricity supply of heat pumps and EV chargers. A USB to RS485 converter is needed to read from the modbus output of the meter such as: https://www.amazon.co.uk/gp/product/B07SD65BVF. The SDM120 meter comes in a number of different variants, be sure to order the version with a modbus output.

**read_interval:** Interval between readings in seconds

```text
[[SDM120]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 2400
        parity = none
        datatype = float
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sdm120
        # prefix = sdm_
        [[[[meters]]]]
            [[[[[sdm120a]]]]]
                address = 1
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
            [[[[[sdm120b]]]]]
                address = 2
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
```
