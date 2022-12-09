# emonHub Interfacers

- [SDS011 Air-Quality sensor](#sds011-air-quality-sensor)
- [SDM120 Modbus single-phase meter](#reading-from-a-sdm120-single-phase-meter)
- [MBUS Reader for electric and heat meters](#mbus-reader-for-electric-and-heat-meters)
- [Direct DS18B20 temperature sensing](#direct-ds18b20-temperature-sensing)
- [Direct Pulse counting](#direct-pulse-counting)
- [Read State of charge of a Tesla Power Wall](#read-state-of-charge-of-a-tesla-power-wall)
- [Modbus: Renogy](#modbus-renogy)
- [SMA Solar](#sma-solar)
- [Victron VEDirect Protocol](#victron-vedirect-protocol)
- [Modbus TCP](#modbus-tcp)
- [Samsung ASHP](#samsung-ashp)

## SDS011 Air-Quality sensor 

1\. Plug the SDS011 sensor into a USB port on either the emonPi or emonBase.

```{image} img/sds011.jpg
:width: 300px
```

2\. Login to the local copy of Emoncms running on the emonPi/emonBase and navigate to Setup > EmonHub. Click on 'Edit Config' and add the following config to the interfacers section to enable reading from the SDS011 sensor:

**readinterval:** Interval between readings in minutes, it is recommended to read every 5 minutes to preserve sensor lifespan.

Example SDS011 EmonHub configuration:

```
[[SDS011]]
    Type = EmonHubSDS011Interfacer
    [[[init_settings]]]
        com_port = /dev/ttyUSB0
    [[[runtimesettings]]]
        readinterval = 5
        nodename = SDS011
        pubchannels = ToEmonCMS,
```

3\. The SDS011 readings will appear on the Emoncms Inputs page within a few minutes and should look like this:

```{image} img/sds011_emoncms.png
:width: 500px
```

**Tip:** When logging the SDS011 inputs to feeds, make sure to set the feed interval to match the sensor readinterval, e.g select 5 minutes if readinterval is set to 5.

---

## Reading from a SDM120 single-phase meter


The [SDM120-Modbus-MID](https://shop.openenergymonitor.com/sdm120-modbus-mid-45a/) single phase electricity meter provides MID certified electricity monitoring up to 45A, ideal for monitoring the electricity supply of heat pumps and EV chargers. A [USB to RS485 converter](https://shop.openenergymonitor.com/modbus-rs485-to-usb-adaptor/) is needed to read from the modbus output of the meter.The SDM120 meter comes in a number of different variants, be sure to order the version with a modbus output (SDM120-MBUS-MID).

1\. Connect up the USB to RS485 converter to the modbus output of the SDM120 meter and plug the converter into a USB port on either the emonPi or emonBase.

```{image} img/sdm120_modbus.png
:width: 400px
```

2\. Login to the local copy of Emoncms running on the emonPi/emonBase and navigate to Setup > EmonHub. Click on 'Edit Config' and add the following config to the interfacers section to enable reading from the SDM120 meter:

**read_interval:** Interval between readings in seconds

Example single SDM120 EmonHub (V2.3.4) configuration:

```
[[SDM120]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sdm120
        # prefix = sdm_
        [[[[meters]]]]
            [[[[[sdm120]]]]]
                address = 1
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
```

EmonHub (V2.3.4) can also possible to read data from multiple SDM120 modbus meters, each meter will need an unique modbus ID, this ID can be set using the push button menu on the SDM120. Example emonhub config multiple  SDM120 EmonHub configuration:

```
[[SDM120]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = sdm120
        # prefix = sdm_
        [[[[meters]]]]
            [[[[[sdm120a]]]]]
                address = 1
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
            [[[[[sdm120b]]]]]
                address = 2
                registers = 0,6,12,18,30,70,72,74,76
                names = V,I,P,VA,PF,FR,EI,EE,RI
                precision = 2,3,1,1,3,3,3,3,3
```

3\. The SDM120 readings will appear on the Emoncms Inputs page within a few seconds and should look like this:

```{image} img/sdm120_emoncms.png
:width: 500px
```

**Tip:** When logging the SDM120 cumulative energy output (sdm_E) to a feed, use the 'log to feed (join)' input processor to create a feed that can work with the delta mode in graphs. This removes any data gaps and makes it possible for the graph to generate daily kWh data on the fly.

---

## MBUS Reader for Electric and Heat meters

Many electricity and heat meters are available with meter bus (MBUS) outputs. Using an [MBUS to USB converter](https://shop.openenergymonitor.com/m-bus-to-usb-converter/), these can be read from an emonPi or emonBase. For heat pumps, this provides a convenient way of monitoring the heat output, flow temperature, return temperature, flow rate and cumulative heat energy provided by the system.

1\. Connect up the USB to MBUS converter to the MBUS output of the meter and plug the converter into a USB port on either the emonPi or emonBase.

```{image} img/mbus_reader.png
:width: 600px
```

2\. Login to the local copy of Emoncms running on the emonPi/emonBase and navigate to Setup > EmonHub. Click on 'Edit Config' and add the following config in the interfacers section to enable reading from the MBUS meter:

- **baud:** The MBUS baud rate is typically 2400 or 4800. It is usually possible to check the baud rate of the meter using the meter configuration interface.
- **read_interval:** Interval between readings in seconds.

List attached meters as shown in the example below.

- **address:** The address of the meter is also usually possible to find and or set via the meter LCD configuration interface. If in doubt try 0 or 254. It's also usually possible to set the ID by MBUS interface [Here is a script](https://github.com/emoncms/usefulscripts/tree/master/mbus) to check and set the address which has been tested to work on Kamstrup Multical 403 and Sontex 531.
- **type:** Available options include: standard, qalcosonic_e3, sontex531, sdm120

**Note:** We've experienced reliability issues reading from the MBUS version of the SDM120 electric meters. We recommend using the Modbus version with a seperate Modbus reader for more reliable results. For more information please see [https://community.openenergymonitor.org/t/sdm120-mbus-meter-freezing-drop-out/20765/2](https://community.openenergymonitor.org/t/sdm120-mbus-meter-freezing-drop-out/20765/2).

### Kamstrup Multical 403

```
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device = /dev/ttyAMA0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = MBUS
        [[[[meters]]]]
            [[[[[heatmeter]]]]]
                address = 1
                type = kamstrup403
```

### Sontex 531

```
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device = /dev/ttyAMA0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = MBUS
        [[[[meters]]]]
            [[[[[heatmeter]]]]]
                address = 1
                type = sontex531
```

### Sontex 789*

```
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device = /dev/ttyAMA0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = MBUS
        [[[[meters]]]]
            [[[[[heatmeter]]]]]
                address = 0
                type = standard
```


**\*Extra Config for Sontex 789**

Note: Sontex 789 requires an additional step, sontex 531 works fine without this extra config:

Sontex 789 and 749 have 3 pages of Mbus info. We're interested in the 3rd page of info. To scroll through the pages

Edit `/opt/openenergymonitor/emonhub/src/interfacers/EmonHubMBUSInterfacer.py`

1. change L402 `self.mbus_short_frame(address, 0x5b)` to `self.mbus_short_frame(address, 0x7b)`

`nano +402 /opt/openenergymonitor/emonhub/src/interfacers/EmonHubMBUSInterfacer.py`

2. restart emonhub
3. change L402 `self.mbus_short_frame(address, 0x7b)` back to `self.mbus_short_frame(address, 0x5b)`
4. restart emonhub

Each change moves the meter on to the next page. Each time after restarting emonHub check the data from the heat meter in the emonHub logs or Emoncms Inputs. Look for data which includes Energy, Power, FlowT and ReturnT.

*The battery powered Sontex 789 receives power via the MBUS reader, thefore battery will last indefinitely.*

### Qalcosonic E3

```
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device = /dev/ttyAMA0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = MBUS
        [[[[meters]]]]
            [[[[[heatmeter]]]]]
                address = 1
                type = qalcosonic_e3
```

### Sharky 775

```
[[MBUS]]
    Type = EmonHubMBUSInterfacer
    [[[init_settings]]]
        device = /dev/ttyAMA0
        baud = 2400
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        validate_checksum = False
        nodename = mbus
        [[[[meters]]]]
            [[[[[heatmeter]]]]]
                address = 25
                type = standard
```

Example heat meter data:

```{image} img/mbus_emoncms.png
:width: 600px
```

**Tip:** When logging the cumulative energy output (Energy) to a feed, use the 'log to feed (join)' input processor to create a feed that can work with the delta mode in graphs. This removes any data gaps and makes it possible for the graph to generate daily kWh data on the fly.

---

## Direct DS18B20 temperature sensing

This EmonHub interfacer can be used to read directly from DS18B20 temperature sensors connected to the GPIO pins on the RaspberryPi. At present a couple of manual setup steps are required to enable DS18B20 temperature sensing before using this EmonHub interfacer.

**Manual RaspberryPi configuration:**

1\. SSH into your RaspberryPi, open /boot/config.txt in an editor:

    sudo nano /boot/config.txt

2\. Add the following to the end of the file:

    dtoverlay=w1-gpio

3\. Exit and reboot the Pi

    sudo reboot
    
4\. SSH back in again and run the following to enable the required modules:

    sudo modprobe w1-gpio
    sudo modprobe w1-therm

**Configuring the Interfacer:**

Login to the local copy of Emoncms running on the emonPi/emonBase and navigate to Setup > EmonHub. Click on 'Edit Config' and add the following config in the interfacers section to enable reading from the temperature sensors.

- **read_interval:** Interval between readings in seconds. 
- **ids:** This can be used to link specific sensors addresses to input names listed under the names property. 
- **names:** Names associated with sensor id's, ordered by index.


Example DS18B20 EmonHub configuration:

```
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

---

## Direct Pulse counting

This EmonHub interfacer can be used to read directly from pulse counter connected to a GPIO pin on the RaspberryPi.

```{image} img/direct_pulse.jpeg
:width: 600px
```

- **pulse_pin:** Pi GPIO pin number must be specified. Create a second interfacer for more than one pulse sensor
- **Rate_limit:** The rate in seconds at which the interfacer will pass data to emonhub for sending on. Too short and pulses will be missed. Pulses are accumulated in this period.
- **nodeoffset:** Default NodeID is 0. Use nodeoffset to set NodeID 

Example Pulse counting EmonHub configuration:

```
[[pulse]]
    Type = EmonHubPulseCounterInterfacer
    [[[init_settings]]]
        pulse_pin = 15
        # bouncetime = 2
        # rate_limit = 2
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        nodeoffset = 3
```

---

## Read State of charge of a Tesla Power Wall

This interfacer fetches the state of charge of a Tesla Power Wall on the local network. Enter your PowerWall IP-address or hostname in the URL section of the following emonhub.conf configuration:

```
[[PowerWall]]
    Type = EmonHubTeslaPowerWallInterfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        name = powerwall
        url = http://POWERWALL-IP/api/system_status/soe
        readinterval = 10
```

---

## Modbus Renogy

See example config:<br>[EmonHub Github: Renogy.emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/master/conf/interfacer_examples/Renogy/Renogy.emonhub.conf)

## SMA Solar

See example config and documentation:<br>[EmonHub Github: SMA Solar](https://github.com/openenergymonitor/emonhub/tree/master/conf/interfacer_examples/smasolar)

## Victron VEDirect Protocol

See example config and documentation:<br>[EmonHub Github: Victron VE.Direct Protocol](https://github.com/openenergymonitor/emonhub/tree/master/conf/interfacer_examples/vedirect)

## Modbus TCP

See example config and documentation:<br>[EmonHub Github: modbus TCP configuration](https://github.com/openenergymonitor/emonhub/tree/master/conf/interfacer_examples/modbus)

## Samsung ASHP

```{image} img/samsung-ashp.jpg
:width: 400px
```

EmonHub (V2.3.4) can read data directly from a Samsung Air Souce Heat Pump (ASHP) or HVAC unit equipped with the [Samsung Modbus Interface MIM-B19](https://midsummerwholesale.co.uk/buy/samsung-heat-pumps/Samsung-modbus-MIM-B19).

Example emonhub config:

```
[[SAMSUNG-ASHP-MIB19N]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyUSB0
        baud = 9600
        parity = even
        datatype = int
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 20
        nodename = samsung-ashp
        # prefix = sdm_
        [[[[meters]]]]
            [[[[[ashp]]]]]
                device_type = samsung
                address = 1
                registers = 75,74,72,65,66,68,52,59,58,2,79,87,5,89
                names = dhw_temp,dhw_target,dhw_status,return_temp,flow_temp,flow_target,heating_status,indoor_temp,indoor_target, defrost_status,away_status,flow_rate,outdoor_temp,3_way_valve
                scales = 0.1,0.1,1,0.1,0.1,0.1,1,0.1,0.1,1,1,0.1,0.1,1
                precision = 2,2,1,2,2,2,1,2,2,1,1,2,2,1
```

Example Samsung ASHP data in Emoncms:

```{image} img/samsung-ashp-emoncms.png
:width: 450px
```

EmonHub also makes this data available via MQTT `emon/samsung-ashp`
