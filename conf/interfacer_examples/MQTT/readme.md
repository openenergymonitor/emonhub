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
