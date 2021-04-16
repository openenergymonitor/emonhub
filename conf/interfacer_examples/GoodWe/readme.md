### Goodwe Interfacer

This interfacer fetches the state of charge of a GoodWe ET inverter on the local network. Enter your GoodWe Wifi IP-address ip section of the following emonhub.conf configuration:

```text
    [[GoodWe]]
        Type = EmonHubGoodWeInterfacer
        [[[init_settings]]]
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            name = goodwe
            ip = 192.168.0.100
            port = 8899
            readinterval = 10
            retries = 3
            timeout = 2
```
