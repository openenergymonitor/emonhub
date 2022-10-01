# Jaguar Land Rover Interfacer #

This interfacer collects data from Jagular Land Rover's InControl API.  Data collected on vehicle state of charge is suitable for use with OpenEVSE via MQTT. 

Tested with Range Rover Velar PHEV.  

## Readings ##

The following values (in order) are determined from the Jaguar Land Rover API.

* ODOMETER_MILES
* EV_STATE_OF_CHARGE
* EV_RANGE_ON_BATTERY_MILES
* EV_RANGE_ON_BATTERY_KM
* EV_CHARGING_RATE_SOC_PER_HOUR
* EV_SECONDS_TO_FULLY_CHARGED
* EV_CHARGING_STATUS (1 or 0)

## Sample config for emonhub.conf ##

Sample configuration, add these settings under the [interfacers] tag.   Changing username and password to match those for your account on https://incontrol.landrover.com/

```
[[JaguarLandRover]]
    Type = EmonHubJaguarLandRoverInterfacer
    [[[init_settings]]]
        timeinverval = 600
        duringchargetimeinterval = 60
        nodeid = 28
        jlrusername = USERNAMEGOESHERE
        jlrpassword = PASSWORDGOESHERE
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
```

## Settings ##

### timeinverval ###
Interval between taking readings from API.  Normally 10 minutes (600 seconds)

### duringchargetimeinterval ###
When charging the API updates more frequently, so update every 1 minute when charging is detected (60 seconds)

### nodeid ###
The emonHub/emonCMS nodeId to use

### jlrusername ###
Username as used in the https://incontrol.landrover.com/ site

### jlrpassword ###
Password as used in the https://incontrol.landrover.com/ site
