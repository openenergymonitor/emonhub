### Tesla Power Wall Interfacer

This interfacer fetches the state of charge of a Tesla Power Wall on the local network. Enter your PowerWall IP-address or hostname in the URL section of the following emonhub.conf configuration:

```text
    [[PowerWall]]
        Type = EmonHubTeslaPowerWallInterfacer
        [[[init_settings]]]
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            name = powerwall
            url = http://POWERWALL-IP/api/system_status/soe
            readinterval = 10
```
