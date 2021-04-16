### Influx Writer

The influx writer uses the 1.0 api to write in bulk (100) every influx_interval in seconds.


- **influx_interval:** The default interval is 30 seconds. For visualization only this should be enough. If you want more details, you can lower this value, but this will put more stress on your system.
- **influx_host:** The host the influx service runs. Defaults to localhost.
- **influx_port:** The port the influx service runs. Defaults to 8086.
- **influx_user:** The user for posting data into the influx db. Defaults to emoncms.
- **influx_passwd:** The password for posting data into the influx db. Defaults to emoncmspw.
- **influx_db:** The database where your timeseries will be stored in the influx db. Defaults to emoncms.



```text
[[Influx]]
    loglevel = DEBUG
    Type = EmonHubInfluxInterfacer
    [[[init_settings]]]
        influx_port = 8086
        influx_host = localhost
        influx_user = grafana
        influx_passwd = samplepw
        influx_db = home

    [[[runtimesettings]]]
        subchannels = ToEmonCMS,
```
