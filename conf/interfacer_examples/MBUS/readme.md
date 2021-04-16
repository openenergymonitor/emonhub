### MBUS Reader for Electric and Heat meters

Many electricity and heat meters are available with meter bus (MBUS) outputs. Using an MBUS to USB converter (coming soon), these can be read from an emonPi or emonBase. For heat pumps, this provides a convenient way of monitoring the heat output, flow temperature, return temperature, flow rate and cumulative heat energy provided by the system.

- **baud:** The MBUS baud rate is typically 2400 or 4800. It is usually possible to check the baud rate of the meter using the meter configuration interface.
- **address:** The address of the meter is also usually possible to find via the meter configuration interface. If in doubt try 0 or 254.
- **Pages:** Some meters such as the Sontex 531 have infomation on multiple MBUS pages (These are 3,1 on the Sontex 531). For other meters just set to 0.
- **read_interval:** Interval between readings in seconds.


```text
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 4800
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        address = 100
        pages = 3,1
        read_interval = 10
        nodename = MBUS
```
