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
webAPI		/solar_api/v1/GetPowerFlowRealtimeData.fcgi
         "E_Day"   		# Eneergy produced for current day
         "E_Total" 		# Lifetime energy produced
         "E_Year" 		# energy produced for current year
         "P"		# Current power output
         "StatusCode"	# inverter status (7 = online, anything else offline)
	 
webAPI		/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&DeviceID=1&DataCollection=3PInverterData&DeviceId=1
         "IAC_L1" 		# current on phase A
         "IAC_L2" 		# current on phase B
         "IAC_L3" 		# current on phase C
         "UAC_L1" 		# Voltage on phase A
         "UAC_L2" 		# Voltage on phase B
         "UAC_L3" 		# Voltage on phase c
	 
webAPI	/solar_api/v1/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0
	Current_AC_Phase_1
	Current_AC_Phase_2
	Current_AC_Phase_3
	EnergyReactive_VArAC_Sum_Consumed
	EnergyReal_WAC_Minus_Absolute
    	EnergyReal_WAC_Plus_Absolute
	EnergyReal_WAC_Sum_Consumed
	EnergyReal_WAC_Sum_Produced
	Frequency_Phase_Average
	Meter_Location_Current
	PowerApparent_S_Phase_1
	PowerApparent_S_Phase_2
	PowerApparent_S_Phase_3
	PowerApparent_S_Sum",
    	PowerFactor_Phase_1
	PowerFactor_Phase_2
	PowerFactor_Phase_3
	PowerFactor_Sum
	PowerReactive_Q_Phase_1
	PowerReactive_Q_Phase_2
 
webAPI	/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System&DeviceId=1
	Current_AC_Phase_1
	Current_AC_Phase_2
	Current_AC_Phase_3
	EnergyReactive_VArAC_Sum_Consumed
	EnergyReactive_VArAC_Sum_Produced
	EnergyReal_WAC_Minus_Absolute
	EnergyReal_WAC_Plus_Absolute
	EnergyReal_WAC_Sum_Consumed
	EnergyReal_WAC_Sum_Produced
	Frequency_Phase_Average
	Meter_Location_Current
	PowerApparent_S_Phase_1
	PowerApparent_S_Phase_2
	PowerApparent_S_Phase_3
	PowerApparent_S_Sum
	PowerFactor_Phase_1
	PowerFactor_Phase_2
	PowerFactor_Phase_3
	PowerFactor_Sum
	PowerReactive_Q_Phase_1
	PowerReactive_Q_Phase_2
	PowerReactive_Q_Phase_3
	PowerReactive_Q_Sum
	PowerReal_P_Phase_1
	PowerReal_P_Phase_2
	PowerReal_P_Phase_3
	PowerReal_P_Sum
	TimeStamp
	Visible
	Voltage_AC_PhaseToPhase_12
	Voltage_AC_PhaseToPhase_23
	Voltage_AC_PhaseToPhase_31
	Voltage_AC_Phase_1
	Voltage_AC_Phase_2
	Voltage_AC_Phase_3


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
