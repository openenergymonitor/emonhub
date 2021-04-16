### SDM120-Modbus

The SDM120-Modbus single phase electricity meter provides MID certified electricity monitoring up to 45A, ideal for monitoring the electricity supply of heat pumps and EV chargers. A USB to RS485 converter is needed to read from the modbus output of the meter such as: https://www.amazon.co.uk/gp/product/B07SD65BVF. The SDM120 meter comes in a number of different variants, be sure to order the version with a modbus output.

**read_interval:** Interval between readings in seconds

```text
[[SDM120]]
    Type = EmonHubSDM120Interfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = SDM120
        # prefix = sdm_
```
