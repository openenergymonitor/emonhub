# Fronius WebAPI Interface #

This is an interface for Fronius Inverter with or without modbus connected power meters.
This interfacer extracts data using api calls to the inverter. It makes available all the data retuned by the api's.
The Fronius Webapi is published on thier website.

It utilises three api calls to extract 3 sets of data
from the URL's  /solar_api/v1/GetPowerFlowRealtimeData.fcgi
                /solar_api/v1/GetInverterRealtimeData.cgi
                /solar_api/v1/GetInverterInfo.cgi
The webapi returns data in json format and the readings are extracted from those responses.

Tested with Fronius Symo 5.0-3-M inverter & Fronous smart meter 63A .

## Readings ##

The following values are extracted from the webapi API.

         "E_Day"   		# Eneergy produced for current day
         "E_Total" 		# Lifetime energy produced
         "E_Year" 		# energy produced for current year
         "P"		# Current power output
         "StatusCode"	# inverter status (7 = online, anything else offline)
         "IAC_L1" 		# current on phase A
         "IAC_L2" 		# current on phase B
         "IAC_L3" 		# current on phase C
         "UAC_L1" 		# Voltage on phase A
         "UAC_L2" 		# Voltage on phase B
         "UAC_L3" 		# Voltage on phase c



## Sample config for emonhub.conf ##

Sample configuration, add these settings under the [interfacers] tag.   

```
### This interfacer manages communication to Fronius Inverter APi for inverter/smart power meter monitoring
[[FroniusWebAPI]]
    Type = EmonHubFroniusAPIInterfacer
    [[[init_settings]]]
	webAPI_IP = 192.168.1.10
	webAPI_port = 80
   [[[runtimesettings]]]
	interval = 10   # time in seconds between checks, This is in addition to emonhub_interfacer.run() sleep time of .01
        nodeId = 122
        pubchannels = ToEmonCMS,

```

## Settings ##

### timeinverval ###
Interval between taking readings from API.  

### nodeid ###
The emonHub/emonCMS nodeId to use. any number as long as it is not already used in the emodhub.conf

### webAPI_IP ###
ip address of the fronius inverter on the network

### webAPI_port ###
Non standard port if configured on the inverter reservered for future use. Not currently implemented. 
