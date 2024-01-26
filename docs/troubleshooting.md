---
github_url: "https://github.com/openenergymonitor/emonhub/blob/master/docs/troubleshooting.md"
---
# emonHub Troubleshooting

```{admonition} emonCMS inputs not updating?
emonHub is a good place to look first. Check the emonHub log and configuration. See below for more details.
```

```{admonition} Unknown nodes keep appearing?
**Turn off autoconf** at the top of emonhub.conf (set autoconf = 0) and **restart emonHub**. Remove the unknown nodes, keep only the nodes that you wish to keep.

Unknown nodes can also be cleared in emoncms with the following URL:

    https://emoncms.org/device/clean.json
    http://emonpi.local/device/clean.json    

``` 

## View the emonHub log

The emonHub log is a useful place to look if you are trying to troubleshoot problems with inputs not updating in emoncms. If `loglevel = DEBUG` is set in the `[hub]` section of the emonHub configuration file, you should see a stream of activity in the emonhub log.

To access the emonHub log from within emonCMS running on the emonPi/emonBase/RaspberryPi. Navigate to Setup > EmonHub.

![emonhublog.png](img/emonhublog.png)

Alternatively the emonHub log can be viewed via command line:

    tail -f /var/log/emonhub/emonhub.log -n1000
    
### Making sense of the log

These messages indicate that a new frame of data is being received, via the interfacer named SPI and on node 17 in this case with the values as indicated. The frame is being sent to the internal emonHub channel `ToEmonCMS`:

```
2022-12-01 09:50:53,993 INFO     SPI        Packet received 52 bytes
2022-12-01 09:50:53,994 DEBUG    SPI        36 NEW FRAME : 
2022-12-01 09:50:53,995 DEBUG    SPI        36 Timestamp : 1669888253.994002
2022-12-01 09:50:53,996 DEBUG    SPI        36 From Node : 17
2022-12-01 09:50:53,996 DEBUG    SPI        36    Values : [3, 240, 11, 11, 11, 5, 5, 5, 0, 0, 0, 0, 0, 0, 19.12, 300, 300, 0, -2, -100.0]
2022-12-01 09:50:53,996 DEBUG    SPI        36      RSSI : -44
2022-12-01 09:50:53,997 DEBUG    SPI        36 Sent to channel(start)' : ToEmonCMS
2022-12-01 09:50:53,997 DEBUG    SPI        36 Sent to channel(end)' : ToEmonCMS
```

In the standard emonSD configuration, data frames received and passed on to the `ToEmonCMS` channel are then published via MQTT. You should see a series of lines that look something like this:

    2022-12-01 09:51:03,218 DEBUG    MQTT       Publishing: emon/emonTx4_17/MSG 1

emonCMS is seperately subscribed to the `emon/` MQTT channel and will show these messages as emoncms inputs.
