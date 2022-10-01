### MBUS Reader for Electric and Heat meters

Many electricity and heat meters are available with meter bus (MBUS) outputs. Using an MBUS to USB converter (coming soon), these can be read from an emonPi or emonBase. For heat pumps, this provides a convenient way of monitoring the heat output, flow temperature, return temperature, flow rate and cumulative heat energy provided by the system.

- **baud:** The MBUS baud rate is typically 2400 or 4800. It is usually possible to check the baud rate of the meter using the meter configuration interface.
- **read_interval:** Interval between readings in seconds.

List attached meters as shown in the example below.

- **address:** The address of the meter is also usually possible to find via the meter configuration interface. If in doubt try 0 or 254.
- **type:** Available options include: standard, qalcosonic_e3, sontex531, sdm120

```text
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device = /dev/ttyAMA0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = MBUS
        [[[[meters]]]]
            [[[[[sdm120]]]]]
                address = 1
                type = sdm120
            [[[[[qalcosonic]]]]]
                address = 2
                type = qalcosonic_e3
```
