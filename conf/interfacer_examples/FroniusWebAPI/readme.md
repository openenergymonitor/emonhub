# Modbus interface

This interface starts a http connection and retrieves inverter and power meter information for publishing via mqtt to emonCMS


## Usage and configuration

There is a sample FroniusWebAPI.emonhub.conf file located in this directory.

### Sample interfacer config within emonhub.conf

Sample configuration for modbus TCP clients

```

### This interfacer manages connections to fronius inverters via webapi
[[FroniusAPI]]
    Type = EmonHubFroniusAPIInterfacer
    [[[init_settings]]]
	webAPI_IP = 192.168.1.11  # ip address of the inverter.
	webAPI_port = 80  # http port the inverter listens on. default is 80 unless changed on the inverter settings.
    [[[runtimesettings]]]
	nodeId = 12
        interval = 20   # time in seconds between checks, This is in addition to emonhub_interfacer.run() sleep time of .01
        pubchannels = ToEmonCMS,

```

### Sample Node declaration in emonhub.conf
Node ID must match node ID set in interfacer definition above

```
[[12]]
    nodename = froniusAPI
```
