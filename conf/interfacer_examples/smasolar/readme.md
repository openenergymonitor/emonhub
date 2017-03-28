# SMA Solar Bluetooth Interface #

This is an interface between SMA Solar inverters (http://www.sma-uk.com/) and emonCMS.

emonHub is used to communicate over bluetooth to the solar inverter and retrieve various generation values, which are posted into emonCMS.

Currently tested on SMA models:

* SB3000
* SB3000HF


## Installation ##

Note that you will need to have a bluetooth USB device installed - recommend a class 1 device with a longer range if your inverter is more than 10 metres away.

On emonPI, you will need to install the bluetooth software library, using the commands

```
rpi-rw
sudo aptitude install bluez python-bluetooth

sudo service bluetooth start
sudo service bluetooth status
sudo hciconfig hci0 up
```


### Finding inverter bluetooth address ###

Run the command "hcitool scan", which should list the bluetooth devices/addresses it can see.
```
Scanning ...
        00:80:25:1D:AC:53       SMA001d SN: 2120051742 SN2120051742
```

## Sample config for emonhub.conf ##

Sample configuration for SMA Solar interface, add these settings under the [interfacers] tag.
```
[[SMASolar]]
    Type = EmonHubSMASolarInterfacer
    [[[init_settings]]]
        inverteraddress= 00:80:25:1D:AC:53
        inverterpincode = 0000
        timeinverval = 5
        nodeid = 29
        packettrace = 0
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
```

## Setting s##

### inverteraddress ###
Specify the bluetooth address of the solar inverter for instance 00:80:25:1D:AC:53

### inverterpincode ###
Security PIN code, normally defaults to "0000" unless you have changed it.

### timeinverval ###
Time in seconds between samples, defaults to 10 seconds

### nodeid ###
Starting node id number to assign to inputs into emonCMS, defaults to 29 for the first inverter, 30 for second, 31 for third etc.

Note, you do *NOT* have to manually enter the nodes into the "[nodes]" section of the config file.

### packettrace ###
If needed, set to 1 to enable debug logging of the bluetooth communication packets.  You will also need to set the debug level for emonHub to DEBUG.
