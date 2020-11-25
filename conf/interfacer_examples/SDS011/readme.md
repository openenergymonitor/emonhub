### SDS011 Air Quality Sensor

Read data from the SDS011 particulate matter sensor. Updated implementation puts sensor to sleep between readings.

**readinterval:** Interval between readings in minutes, it is recommended to read every 5 minutes to preserve sensor lifespan.

```text
[[SDS011]]
    Type = EmonHubSDS011Interfacer
    [[[init_settings]]]
        com_port = /dev/ttyUSB0
    [[[runtimesettings]]]
        readinterval = 5
        nodename = SDS011
        pubchannels = ToEmonCMS,
```
