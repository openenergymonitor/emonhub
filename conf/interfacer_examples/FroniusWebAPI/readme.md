# Fronius Web API interface

This interface starts a http connection and retrieves inverter and power meter information for publishing via mqtt to emonCMS
The Web API is documented in detail on the Fronius Web site. The PDF can be downloaded here https://www.fronius.com/en/solar-energy/installers-partners/products/all-products/system-monitoring/open-interfaces/fronius-solar-api-json-

## Usage and configuration

There is a sample FroniusWebAPI.emonhub.conf file located in this directory.

### Sample interfacer config within emonhub.conf

Sample configuration for modbus TCP clients
All inputs are derived from the webapi json output

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
## Sample web api responses.

/solar_api/v1/GetInverterInfo.cgi
```
{
   "Body" : {
      "Data" : {
         "1" : {
            "CustomName" : "&#83;&#121;&#109;&#111;&#32;&#53;&#46;&#48;&#45;&#51;&#45;&#77;&#32;&#40;&#49;&#41;",
            "DT" : 122,
            "ErrorCode" : 0,
            "PVPower" : 6600,
            "Show" : 1,
            "StatusCode" : 7,
            "UniqueID" : "0"
         }
      }
   },
   "Head" : {
      "RequestArguments" : {},
      "Status" : {
         "Code" : 0,
         "Reason" : "",
         "UserMessage" : ""
      },
      "Timestamp" : "2024-12-28T14:01:39+08:00"
   }
}
```
/solar_api/v1/GetPowerFlowRealtimeData.fcgi

```
{
   "Body" : {
      "Data" : {
         "Inverters" : {
            "1" : {
               "DT" : 122,
               "E_Day" : 21288,
               "E_Total" : 93495504,
               "E_Year" : 9019699,
               "P" : 4797
            }
         },
         "Site" : {
            "E_Day" : 21288,
            "E_Total" : 93495504,
            "E_Year" : 9019699,
            "Meter_Location" : "grid",
            "Mode" : "meter",
            "P_Akku" : null,
            "P_Grid" : -3829.8899999999999,
            "P_Load" : -967.11000000000013,
            "P_PV" : 4797,
            "rel_Autonomy" : 100,
            "rel_SelfConsumption" : 20.160725453408382
         },
         "Version" : "12"
      }
   },
   "Head" : {
      "RequestArguments" : {},
      "Status" : {
         "Code" : 0,
         "Reason" : "",
         "UserMessage" : ""
      },
      "Timestamp" : "2024-12-28T12:42:44+08:00"
   }
}
```

/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&DeviceID=1&DataCollection=3PInverterData&DeviceId=1
```
{
   "Body" : {
      "Data" : {
         "IAC_L1" : {
            "Unit" : "A",
            "Value" : 6.4699999999999998
         },
         "IAC_L2" : {
            "Unit" : "A",
            "Value" : 6.5700000000000003
         },
         "IAC_L3" : {
            "Unit" : "A",
            "Value" : 6.54
         },
         "UAC_L1" : {
            "Unit" : "V",
            "Value" : 242.30000000000001
         },
         "UAC_L2" : {
            "Unit" : "V",
            "Value" : 245
         },
         "UAC_L3" : {
            "Unit" : "V",
            "Value" : 245.5
         }
      }
   },
   "Head" : {
      "RequestArguments" : {
         "DataCollection" : "3PInverterData",
         "DeviceClass" : "Inverter",
         "DeviceId" : "1",
         "Scope" : "Device"
      },
      "Status" : {
         "Code" : 0,
         "Reason" : "",
         "UserMessage" : ""
      },
      "Timestamp" : "2024-12-28T12:47:39+08:00"
   }
}
```
