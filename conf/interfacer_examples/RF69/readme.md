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

Steps to get working:

1. Enable SPI in raspi-config:
2. sudo adduser emonhub spi
3. sudo apt-get install python3-spidev (may just upgrade an existing package)
