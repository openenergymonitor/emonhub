# emonHub Overview

EmonHub is a piece of software running on the emonPi and emonBase that can read/subscribe or send/publish data to and from a multitude of services. It is primarily used as the bridge between the OpenEnergyMonitor monitoring hardware and the Emoncms software but it can also be used to read in data from a number of other sources, providing an easy way to interface with a wider range of sensors.

```{admonition} emonCMS inputs not updating?
emonHub is a good place to look first. [Check the emonHub log](#view-the-emonhub-log) and configuration. See below for more details.
```

## Default configuration

The default emonhub configuration file shipped with the `emonSD-10Nov22` image can be found here:
[https://github.com/openenergymonitor/emonhub/blob/master/conf/default.emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/master/conf/default.emonhub.conf)

The previous default emonhub configuration file installed on emonPi systems can be found here: [https://github.com/openenergymonitor/emonhub/blob/master/conf/emonpi.default.emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/master/conf/emonpi.default.emonhub.conf)

Please see the [emonHub configuration guide](configuration.md) for an explanation of the emonHub configuration contents.

## Editing the emonHub configuration file

For users with an emonPi/emonBase or RaspberryPi running emonSD, emonHub can be configured from within emonCMS. Navigate to Setup > EmonHub > Edit Config:

![emonhubconf.png](img/emonhubconf.png)

Alternatively the emonHub configuration can be edited in the config file directly via command line:

    nano /etc/emonhub/emonhub.conf

In most cases, EmonHub will automatically update to use the latest configuration. If a change does not update, emonHub can be restarted either by clicking on 'Restart' on the emonCMS > EmonHub page, or by restarting via command line:

    sudo systemctl restart emonhub

Please see the [emonHub configuration guide](configuration.md) for an explanation of the emonHub configuration contents.

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

