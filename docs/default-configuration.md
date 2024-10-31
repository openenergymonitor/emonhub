---
github_url: "https://github.com/openenergymonitor/emonhub/blob/master/docs/default-configuration.md"
---
# emonHub Default Configuration

## Default configuration files

The default emonhub configuration file shipped with the `emonSD-10Nov22` image can be found here:
[https://github.com/openenergymonitor/emonhub/blob/master/conf/default.emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/master/conf/default.emonhub.conf)

The previous default emonhub configuration file installed on emonPi systems can be found here: [https://github.com/openenergymonitor/emonhub/blob/master/conf/emonpi.default.emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/master/conf/emonpi.default.emonhub.conf)

The default interfacers employed are

* **EmonPi2:** *EmonHubOEMInterfacer* - serial data over ttyAMA0, e.g emonPi CT data
* **USB0:** *EmonHubOEMInterfacer* - serial data over ttyUSB0, e.g emonTx4 connected via USB
* **SPI:** *EmonHubRFM69LPLInterfacer* - emonPi2 or rfm69spi radio receiver
* **DS18B20** *EmonHubDS18B20Interfacer* - reads temperature data from connected DS18B20 temperature sensors on the emonPi2
* **MQTT:** *EmonHubRFM69LPLInterfacer* - publish data from above via MQTT
* **emoncmsorg:** *EmonHubEmoncmsHTTPInterfacer* - publish data from above via HTTP

### [[EmonPi2]]

The `[[EmonPi2]]` interfacer section contains the settings to read data via GPIO internal serial port `/dev/ttyAMA0` from an attached emonPi v1 or v2. **Note that serial baud rated differ for different hardware:**

- RFM12Pi: 9600
- RFM69Pi: 38400
- emonPi v1: 38400
- emonPi v2: 115200

```text
[[EmonPi2]]
    Type = EmonHubOEMInterfacer
    [[[init_settings]]]
        com_port = /dev/ttyAMA0
        com_baud = 38400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        subchannels = ToRFM12,
```

### [[USB0]]

This interfacer is present to enable reading of data from an EmonTx4 connected to the emonPi/emonBase via USB. This interfacer can be left in place even if no devices are connected via USB serial.

```text
[[USB0]]
    Type = EmonHubOEMInterfacer
    [[[init_settings]]]
        com_port = /dev/ttyUSB0
        com_baud = 115200
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        subchannels = ToRFM12,
        nodename = emonTx4
```

EmonHub can handle wildcard USB devices e.g any device on a ttyUSB:

`com_port = /dev/ttyUSB*`

It's also possible to specify a VID / PID of a USB device and emonHub will search for that device e.g here's an example of an MBUS reader 

```
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device_vid = 1659
        device_pid = 9123
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = heatpump
        [[[[meters]]]]
            [[[[[heatmeter]]]]]
                address = 1
                type = standard
```

For other USB emonHub examples see [forum thread](https://community.openenergymonitor.org/t/emonhub-automatic-serial-device-detection-for-mbus-and-modbus-interfacers/27025)

### [[SPI]]

This interfacer is used to read from a SPI connected RFM69 radio module. This may be on the emonPi2 board or on the rfm69spi board.

**rfm69spi configuration:**

```test
[[SPI]]
    Type = EmonHubRFM69LPLInterfacer
    [[[init_settings]]]
        nodeid = 5
        networkID = 210
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
```

**emonPi2 configuration (resetPin = 24 and selPin = 16)**

```test
[[SPI]]
    Type = EmonHubRFM69LPLInterfacer
    [[[init_settings]]]
        nodeid = 5
        networkID = 210
        resetPin = 24
        selPin = 16
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
```

### [[DS18B20]]

This interfacer is used to read from DS18B20 temperature sensors directly and is used on the emonPi2 to read from temperature sensors plugged into the temperature input terminals on the side of the unit. 

The temperature sensor data pin is connected to RaspberryPi GPIO17 and this pin is configured in */boot/config.txt.*

```test
[[DS18B20]]
    Type = EmonHubDS18B20Interfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sensors
        # ids = 28-000008e2db06, 28-000009770529, 28-0000096a49b4
        # names = ambient, cyl_bot, cyl_top
```

### [[MQTT]]

Emonhub supports publishing to MQTT topics using the EmonHubMqttInterfacer. The default configuration looks like this:

```text
[[MQTT]]
    Type = EmonHubMqttInterfacer
    [[[init_settings]]]
        mqtt_host = 127.0.0.1
        mqtt_port = 1883
        mqtt_user = emonpi
        mqtt_passwd = emonpimqtt2016
    
    [[[runtimesettings]]]
        pubchannels = ToRFM12,
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

There are three different MQTT topic message formats to choose from:

- **Node variable format - enabled by default**
- Node only format - disabled by default
- JSON format - disabled by default

#### **1. Node variable format (standard)**

(default base topic is `emon`)

```text
    topic: basetopic/emontx/power1
    payload: 100
```

The 'Node variable format' is the current default format. It's a more generic MQTT publishing format that can more easily be used by external applications such as NodeRED, OpenHab and HomeAssistant. This format is also used with the emoncms `emoncms_mqtt.service` to bring data into emoncms.

#### **2. Node only format (disabled by default)**

(default base topic is `emonhub`)

```text
    topic: basetopic/rx/10/values
    payload: 100,200,300
```


#### **3. JSON format (disabled by default)**

This forat exports the data as a single JSOn string with key:value pairs. The timestamp is automatically added and used for the input time to emoncms. The RSSI is added if available (RF in use).

(default base topic is `emon`)

```text
topic: basetopic/<noeid>
payload: {"key1":value1, "key2":value2, .... "time":<timestamp>, "rssi":<rssi>}
```

### [[emoncmsorg]]

The EmonHubEmoncmsHTTPInterfacer configuration that is used for sending data to emoncms.org (or any instance of emoncms). If you wish to use emoncms.org the only change to make here is to replace the blank apikey with your write apikey from emoncms.org found on the user account page.

```text
[[emoncmsorg]]
    Type = EmonHubEmoncmsHTTPInterfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToRFM12,
        subchannels = ToEmonCMS,
        url = https://emoncms.org
        apikey = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        senddata = 1     # Enable sending data to Emoncms.org
        sendnames = 1    # Send full input names (compression will be automatically enabled)
        interval = 30    # Bulk send interval to Emoncms.org in seconds
```

- `senddata`: Enable the sending of data.
- `sendnames`: Send input names (this also automatically enables compression).
- `interval`: Data upload interval in seconds. Increase this to reduce bandwidth, 30s is a minimum value to provide responsive data on the target server, to reduce bandwidth we would recommend using 300-900s.

**Posting to multiple emoncms servers**

You can create more than one of these sections to send data to multiple emoncms instances. For example, if you wanted to send to an emoncms running at emoncms.example.com (or on a local LAN) you would add the following underneath the `emoncmsorg` section described above:

```text
[[emoncmsexample]]
    Type = EmonHubEmoncmsHTTPInterfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToRFM12,
        subchannels = ToEmonCMS,
        url = https://emoncms.example
        apikey = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        senddata = 1     # Enable sending data to Emoncms.org
        sendnames = 1    # Send full input names (compression will be automatically enabled)
        interval = 30    # Bulk send interval to Emoncms.org in seconds
```

This time, the API key will be the API key from your account at emoncms.example.com.
