---
github_url: "https://github.com/openenergymonitor/emonhub/blob/master/docs/default-configuration.md"
---
# emonHub Default Configuration

## Default configuration files

The default emonhub configuration file shipped with the `emonSD-10Nov22` image can be found here:
[https://github.com/openenergymonitor/emonhub/blob/master/conf/default.emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/master/conf/default.emonhub.conf)

The previous default emonhub configuration file installed on emonPi systems can be found here: [https://github.com/openenergymonitor/emonhub/blob/master/conf/emonpi.default.emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/master/conf/emonpi.default.emonhub.conf)

The default interfacers employed are

* RFM data decoding
* MQTT
* HTTP to emoncms.org

### [[RFM2Pi]]

The `[[RFM2Pi]]` interfacer section contains the settings to read from RFM69Pi / emonPi boards via GPIO internal serial port `/dev/ttyAMA0`. The default serial baud on all emonPi and RFM69Pi is `38400`. Older RFM12Pi boards using `9600` baud.

The frequency and network group must match the hardware and other nodes on the network.

The `calibration` config is used to set the calibration of the emonPi when using USA AC-AC adapters 110V. Set `calibration = 110V` when using USA AC-AC adapter.

```text
[[RFM2Pi]]
    Type = EmonHubJeeInterfacer
    [[[init_settings]]]
        com_port = /dev/ttyAMA0
        com_baud = 38400                        # 9600 for old RFM12Pi
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        subchannels = ToRFM12,

        group = 210
        frequency = 433
        baseid = 5                              # emonPi / emonBase nodeID
        quiet = true                            # Report incomplete RF packets (not implemented on emonPi)
        calibration = 230V                      # (UK/EU: 230V, US: 110V)
        # interval =  0                         # Interval to transmit time to emonGLCD (seconds)
```

### [[MQTT]]

Emonhub supports publishing to MQTT topics through the EmonHubMqttInterfacer, defined in the interfacers section of emonhub.conf.

There are two formats that can be used for publishing node data to MQTT:

#### **1. Node only format**

(default base topic is `emonhub`)

```text
    topic: basetopic/rx/10/values
    payload: 100,200,300
```

The 'node only format' is used with the emoncms Nodes Module (now deprecated on Emoncms V9+) and the emonPiLCD python service.

#### **2. Node variable format**

(default base topic is `emon`)

```text
    topic: basetopic/emontx/power1
    payload: 100
```

The 'Node variable format' is the current default format from Emoncms V9. It's a more generic MQTT publishing format that can more easily be used by applications such as NodeRED and OpenHab. This format can also be used with the emoncms `phpmqtt_input.php` script in conjunction with the emoncms inputs module. See [User Guide > Technical MQTT](https://guide.openenergymonitor.org/technical/mqtt/).

#### **3. JSON format**

##### Defaults

```python
'node_format_enable': 1,
'node_format_basetopic': 'emonhub/',
'nodevar_format_enable': 0,
'nodevar_format_basetopic': "nodes/",
'node_JSON_enable': 0,
'node_JSON_basetopic': "emon/"
```

Emoncms default base topic that it listens for is `emon/`.

```text
topic: basetopic/<noeid>
payload: {"key1":value1, "key2":value2, .... "time":<timestamp>, "rssi":<rssi>}
```

This forat exports the data as a single JSOn string with key:value pairs. The timestamp is automatically added and used for the input time to emoncms. The RSSI is added if available (RF in use).

### Default `[MQTT]` config

Note - the trailing `/` is required on the topic definition.

```text
[[MQTT]]

    Type = EmonHubMqttInterfacer
    [[[init_settings]]]
        mqtt_host = 127.0.0.1
        mqtt_port = 1883
        mqtt_user = emonpi
        mqtt_passwd = emonpimqtt2016

    [[[runtimesettings]]]
        # pubchannels = ToRFM12,
        subchannels = ToEmonCMS,

        # emonhub/rx/10/values format
        # Use with emoncms Nodes module
        node_format_enable = 0
        node_format_basetopic = emonhub/

        # emon/emontx/power1 format - use with Emoncms MQTT input
        # http://github.com/emoncms/emoncms/blob/master/docs/RaspberryPi/MQTT.md
        nodevar_format_enable = 1
        nodevar_format_basetopic = emon/

        # Single JSON payload published  - use with Emoncms MQTT
        node_JSON_enable = 0
        node_JSON_basetopic = emon/
```

To enable one of the formats set the `enable` flag to `1`.  More than one format can be used simultaneously.

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
