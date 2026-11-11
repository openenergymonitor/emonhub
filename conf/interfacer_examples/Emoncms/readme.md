### [[emoncmsorg]]

The EmonHubEmoncmsHTTPInterfacer configuration that is used for sending data to emoncms.org (or any instance of emoncms). If you wish to use emoncms.org the only change to make here is to replace the blank apikey with your write apikey from emoncms.org found on the user account page. See [Setup Guide > Setup > Remote logging](https://guide.openenergymonitor.org/setup/remote).

```text
    [[emoncmsorg]]
        Type = EmonHubEmoncmsHTTPInterfacer
        [[[init_settings]]]
        [[[runtimesettings]]]
            pubchannels = ToRFM12,
            subchannels = ToEmonCMS,
            url = https://emoncms.org
            apikey = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            senddata = 1
            sendnames = 1
            compress = 1
```

`senddata` - Set to 0 to stop sending data.

`sendnames` - sends input names in addition to values, makes sure compress is also enabled.

`compress` - compress data, particularly important if sendnames is enabled as this effectively removes the overhead of adding in the names to every packet. Compress is enabled automatically if sendnames is enabled.

You can create more than one of these sections to send data to multiple emoncms instances. For example, if you wanted to send to an emoncms running at emoncms.example.com (or on a local LAN) you would add the following underneath the `emoncmsorg` section described above:

```text
    [[emoncmsexample]]
        Type = EmonHubEmoncmsHTTPInterfacer
        [[[init_settings]]]
        [[[runtimesettings]]]
            pubchannels = ToRFM12,
            subchannels = ToEmonCMS,
            url = https://emoncms.example.com
            apikey = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            senddata = 1
            sendnames = 1
            compress = 1
```

This time, the API key will be the API key from your account at emoncms.example.com.
