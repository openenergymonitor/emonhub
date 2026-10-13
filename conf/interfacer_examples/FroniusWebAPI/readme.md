# Fronius Web API interfacer

Reads a Fronius inverter, and the smart meter connected to it, over the Fronius Solar API on the local network. The Solar API may need to be enabled first in the inverter's web interface; it is off by default on newer GEN24 firmware.

The Solar API is documented by Fronius: [Fronius Solar API (JSON)](https://www.fronius.com/en/solar-energy/installers-partners/products/all-products/system-monitoring/open-interfaces/fronius-solar-api-json-)

## Configuration

Copy [FroniusWebAPI.emonhub.conf](FroniusWebAPI.emonhub.conf) into the `[interfacers]` section of emonhub.conf:

```
[[Fronius]]
    Type = EmonHubFroniusAPIInterfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        name = fronius
        host = 192.168.1.11
        readinterval = 10
```

| Setting | Default | Description |
|---|---|---|
| `name` | `fronius` | emoncms node name |
| `host` | | IP address or hostname of the inverter. Add `:port` if the web interface is not on port 80 |
| `readinterval` | `10` | Seconds between reads |
| `device_id` | `1` | Inverter device id, used for the status and phase values |

No `[nodes]` entry is needed: inputs are published by name.

## Inputs

| Input | Unit | Source |
|---|---|---|
| `pv_power` | W | PV production. Published as 0 while the inverter is asleep |
| `grid_power` | W | Positive importing from the grid, negative exporting. Needs a Fronius smart meter |
| `load_power` | W | Household consumption, negative while consuming (Fronius convention). Needs a smart meter |
| `battery_power` | W | Positive discharging, negative charging. Only with a battery |
| `day_energy` | Wh | PV energy today. Not reported by some models, e.g. GEN24 |
| `total_energy` | Wh | Lifetime PV energy |
| `inverter_status` | | Inverter status code: 0-6 starting up, 7 running, 8 standby, 9 boot loading, 10 error |
| `voltage_l1`, `voltage_l2`, `voltage_l3` | V | Phase voltages, three phase inverters while running |
| `current_l1`, `current_l2`, `current_l3` | A | Phase currents, three phase inverters while running |

Power, energy and the smart meter values are system totals from `GetPowerFlowRealtimeData`, so they include all inverters in a Fronius Solar Net. The status and phase values are for the inverter set by `device_id`.

An input the system does not report is left out rather than published as 0. If the inverter cannot be reached nothing is published, so emoncms shows a gap. A warning is logged when reads start failing and again when the inverter is reachable.

To log PV generation in emoncms, use `Log to feed` on `pv_power` and `Wh Accumulator` on `total_energy`. To log household consumption as a positive value, add `x -1` before logging `load_power`.

## Sample Solar API responses

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
