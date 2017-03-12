#SMA Solar Bluetooth Interface#

This is an interface between SMA Solar inverters (http://www.sma-uk.com/) and emonCMS.

emonHub is used to communicate over bluetooth to the solar inverter and retrieve various generation values, which are posted into emonCMS.

##Sample config for emonhub.conf ##

Sample configuration for SMA Solar interface, add these settings under the [interfacers] tag.

[[SMASolar]]
    Type = EmonHubSMASolarInterfacer
    [[[init_settings]]]
        inverteraddress= 00:80:25:1D:AC:53
        inverterpincode = 0000
        timeinverval = 5
        nodeid = 29
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,

##Settings##

###inverteraddress###
Specify the bluetooth address of the solar inverter for instance 00:80:25:1D:AC:53

###inverterpincode###
Security PIN code, normally defaults to "0000" unless you have changed it.

###timeinverval###
Time in seconds between samples, defaults to 10 seconds

###nodeid###
Starting node id number to assign to inputs into emonCMS, defaults to 29 for the first inverter, 30 for second, 31 for third etc.

Note, you do *NOT* have to manually enter the nodes into the "[nodes]" section of the config file.
