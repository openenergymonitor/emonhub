# BMW Connected Drive Interface #

This is an interface between BMW Connected Drive cars (https://www.bmw-connecteddrive.co.uk) and emonCMS.

Tested with BMW i3 electric car.  This input emulates the same API calls that the www.bmw-connecteddrive.co.uk site uses.

## Readings ##

The following values are extracted from the BMW API.

* battery_size_max
* beMaxRangeElectricKm
* beMaxRangeElectricMile
* beRemainingRangeElectricKm
* beRemainingRangeElectricMile
* beRemainingRangeFuelKm
* beRemainingRangeFuelMile
* fuelPercent
* kombi_current_remaining_range_fuel
* chargingLevelHv
* mileage
* remaining_fuel
* soc_hv_percent
* ChargingActive
* rssi

## Sample config for emonhub.conf ##

Sample configuration, add these settings under the [interfacers] tag.   Changing username and password to match those on https://www.bmw-connecteddrive.co.uk

```
### This interfacer manages communication to BMW API for electric car monitoring
[[BMWi3]]
    Type = EmonHubBMWInterfacer
    [[[init_settings]]]
        timeinverval =600
        duringchargetimeinterval=60
        nodeid = 28
        tempcredentialfile = /tmp/bmwcredentials.json
        bmwapiusername = USERNAMEGOESHERE
        bmwapipassword = PASSWORDGOESHERE
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,

```

## Settings ##

### timeinverval ###
Interval between taking readings from API.  Normally 10 minutes (600 seconds) - the car only updates every few hours so dont flood BMW servers

### duringchargetimeinterval ###
When charging the API updates more frequently, so update every 1 minute when charging is detected (60 seconds)

### nodeid ###
The emonHub/emonCMS nodeId to use

### tempcredentialfile ###
File where temporary access credentials are persisted across emonHub restarts.

### bmwapiusername ###
Username as used in the https://www.bmw-connecteddrive.co.uk site

### bmwapipassword ###
Password as used in the https://www.bmw-connecteddrive.co.uk site
