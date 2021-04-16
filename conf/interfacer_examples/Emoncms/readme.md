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
            sendstatus = 1
```

`sendstatus` - It is possible to the EmonHubEmoncmsHTTPInterfacer to send a 'ping' to the destination emoncms that can be picked up by the myip module which will then list the source IP address. This can be useful for remote login to a home emonpi if port forwarding is enabled on your router.

`senddata` - If you only want to send the ping request, and no data, to emoncms.org set this to 0

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
            sendstatus = 1
```

This time, the API key will be the API key from your account at emoncms.example.com.
