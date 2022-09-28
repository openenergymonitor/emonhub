### RF69 Interfacer

Read data directly from a RFM69cw module on a RaspberryPi:

```text
    [[SPI]]
        Type = EmonHubRF69Interfacer
        [[[init_settings]]]
            nodeid = 5
            group = 210
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
```
