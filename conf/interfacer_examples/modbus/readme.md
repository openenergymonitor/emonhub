# Modbus interface

This interface starts a modbus TCP connection and retrieves register information for publishing via mqtt to emonCMS
For a FRONIUS Inverter specific config to log inver `model/brand/software`
versions on init to the log file change the Type setting to EmonFroniusModbusTcpInterfacer

## Usage and configuration

There is a sample modbusTCP.emonhub.conf file located in this directory.
The rType and datacodes must match. Use the table below to assist.

### Sample interfacer config within emonhub.conf

Sample configuration for modbus TCP clients

```
    [[ModbusTCP]]
        # this interfacer retrieves register information from modbusTCP clients
        # retrieve register information from modbus TCP documentation for your inverter.
        Type = EmonModbusTcpInterfacer
        [[[init_settings]]]
            modbus_IP = 192.168.1.10   # ip address of client to retrieve data from
            modbus_port = 502          # Portclient listens on
        [[[runtimesettings]]]
            # List of starting registers for items listed above
            register = 40118,40092,40102,502,40285,40305,40284,40304,40086,40088,40090
            # nodeid used to match with node definition in nodes section below. Can be set to any integer value not previously used.
            nodeId = 12
            # Channel to publish data to should leave as ToEmonCMS
            pubchannels = ToEmonCMS,
            # time in seconds between checks, This is in addition to emonhub_interfacer.run() sleep time of .01
            # use this value to set the frequency of data retrieval from modbus client
            interval = 10
```

The default unit or slave number is 1. To use a different unit for all registers set `unit`. To query registers from different slaves, add a `nUnit` key, and specify as many numbers as there are registers to query.

```
[[[runtimesettings]]]
    register = 305, 306, 314, 321, 0xA001
    # unit number for each Register
    nUnit = 2, 2, 2, 2, 3
```

### Optional runtime settings

| Setting | Default | Description |
|---|---|---|
| `unit` | `1` | Modbus unit (slave) id used for all registers, unless `nUnit` is given |
| `zero_based` | `false` | By default registers are numbered from 1 (e.g. 40001) and 1 is subtracted before the request is sent. Set to `true` when the device documentation lists the 0-based protocol address |
| `word_order` | `big` | Order of the 16 bit registers in 32 and 64 bit values. `big`: most significant register first (most devices). `little`: least significant register first |
| `max_block_size` | `1` | Maximum number of registers read in one request. With the default of 1 every value is read with its own request. Set up to `125` to read consecutive registers in a single request. Only registers listed next to each other in `register`, and whose addresses directly follow each other, are combined, so list registers in ascending order to benefit. If a device rejects a combined read, lower or remove this setting |

If any read fails, the whole frame is dropped so that values never shift position.

### Sample Node declaration in emonhub.conf
Node ID must match node ID set in interfacer definition above

```
    [[12]]
        nodename = fronius
        [[[rx]]]
            # list of names of items being retrieved
            # This example retrieves the Inverter status, AC power in watts being produced, AC Lifetime KWh produced,
            # KWh produced for current day,....
            names = Inverter_status,AC_power_watts,AC_LifetimekWh,DayWh,mppt1,mppt2,Vmppt1,Vmppt2,PhVphA,PhVphB,PhVphC
            datacodes = H,f,f,Q,H,H,H,H,f,f,f
            scales = 1,0.1,0.1,1,1,1,1,1,0.1,0.1,0.1
            units = V,W,kWh,Wh,W,W,V,V,V,V,V
```

### Datacodes

| Datacode | Type | Registers |
|---|---|---|
| `h` / `H` | 16 bit signed / unsigned integer | 1 |
| `i` or `l` / `I` or `L` | 32 bit signed / unsigned integer | 2 |
| `q` / `Q` | 64 bit signed / unsigned integer | 4 |
| `f` | 32 bit float, sent multiplied by 10: use a scale of `0.1` | 2 |
| `d` | 64 bit float, sent multiplied by 10: use a scale of `0.1` | 4 |

## enecess ecoMain

The [enecess ecoMain](https://www.enecess.eu/de/products/ecomain) measures a three-phase grid circuit and 10 branch circuits. Up to three ecoSub units add 10 branch circuits each. [ecomain.emonhub.conf](ecomain.emonhub.conf) is a complete example with two interfacers and nodes:

- `ecomain_grid` (node 30): grid import/export energy, total and per-phase power, and per-phase voltage, current and power factor. 15 values in 4 requests.
- `ecomain_circuits` (node 31): import/export energy, power, voltage, current and power factor for ecoMain branch circuits 1..10. 60 values in 4 requests.

The ecoMain specific settings are `unit = 255`, `zero_based = true` (addresses in the ecoMain Modbus manual are 0-based), `word_order = little` and `max_block_size = 125`. Values are read only, using function code 03.

The register map below requires ecoMain software version 139 or later.

Each interfacer opens its own connection to the ecoMain. To use a single connection, the two register lists (and the matching names, datacodes and scales) can be combined into one interfacer and node.

### Register map

All registers are holding registers with 0-based addresses. Scales convert to the units shown.

Grid circuit:

| Value | Address | Datacode | Scale | Unit |
|---|---|---|---|---|
| Import energy | 12 | Q | 0.000001 | kWh |
| Export energy | 28 | Q | 0.000001 | kWh |
| Power L1, L2, L3 | 1000, 1002, 1004 | i | 0.01 | W |
| Total power | 1006 | i | 0.01 | W |
| Voltage L1, L2, L3 | 1200, 1203, 1206 | H | 0.01 | V |
| Current L1, L2, L3 | 1201, 1204, 1207 | H | 0.01 | A |
| Power factor L1, L2, L3 | 1202, 1205, 1208 | h | 0.01 | |

Branch circuits, for device `d` (0 = ecoMain, 1..3 = ecoSub 1..3) and channel `c` (1..10):

| Value | Address | Datacode | Scale | Unit |
|---|---|---|---|---|
| Import energy | 32 + 40d + 4(c-1) | Q | 0.000001 | kWh |
| Export energy | 192 + 40d + 4(c-1) | Q | 0.000001 | kWh |
| Power | 1008 + 20d + 2(c-1) | i | 0.01 | W |
| Voltage | 1209 + 30d + 3(c-1) | H | 0.01 | V |
| Current | 1210 + 30d + 3(c-1) | H | 0.01 | A |
| Power factor | 1211 + 30d + 3(c-1) | h | 0.01 | |

Start addresses of channel 1 for each device:

| Device | Import energy | Export energy | Power | Voltage |
|---|---|---|---|---|
| ecoMain | 32 | 192 | 1008 | 1209 |
| ecoSub 1 | 72 | 232 | 1028 | 1239 |
| ecoSub 2 | 112 | 272 | 1048 | 1269 |
| ecoSub 3 | 152 | 312 | 1068 | 1299 |

To read an ecoSub, copy the `ecoMain_circuits` interfacer and node, give them a new node id, and add the offsets above to each register. For example, ecoSub 1 uses `72,76,...,108` for import energy and `1028,1030,...,1046` for power.

### Inverting a circuit

If a current transformer is fitted the wrong way round, set the scale of that circuit's power and power factor to `-0.01`, and swap the names of its import and export energy values.

### Three-phase loads on branch circuits

A three-phase load on three branch circuits is published as three separate sets of values. In Emoncms, use the `+ input` process on the input processing page to add the phase powers into a total, then log it to a feed.
