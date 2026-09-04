# ecoMain Interfacer Configuration

The ecoMain interfacer reads measurements from an ecoMain and its branch circuits over Modbus TCP and publishes logical meters to Emoncms. It does not provide a dedicated device wizard. In Emoncms, open `Setup > EmonHub > Edit Config`, copy the contents of [ecomain.emonhub.conf](ecomain.emonhub.conf) into the `interfacers` section, and adjust the settings for the local network and circuit allocation.

## Devices and Logical Meters

Each `EmonHubEcoMainInterfacer` instance represents one physical ecoMain device. Entries under `meters` are user-defined logical meter instances, not additional physical devices. Each logical meter appears on the Emoncms Inputs page under its own `nodeid` and `nodename`.

- `source = grid` reads the ecoMain's fixed three-phase grid circuit. Do not configure `phases`. An interfacer may contain at most one `grid` logical meter.
- `source = branches` combines physical branch circuits into a single-phase or three-phase logical meter. Each `phases` entry uses the `device:channel:invert` format. `device` must be `0..3` (`0` is the ecoMain and `1..3` are ecoSub 1..3), `channel` must be `1..10`, and `invert` must be `true` or `false`. One entry defines a single-phase meter; three entries define L1, L2, and L3 in configuration order.
- A physical branch identified by the same `device:channel` pair cannot be assigned more than once, either across logical meters or within one logical meter. Every logical meter must have a unique `nodeid` and a unique `nodename`.
- `nodename` is the node name published to MQTT and displayed on the Emoncms Inputs page. It may contain Unicode letters and digits, underscores, spaces, periods, and hyphens. It must not contain `/`, `#`, `+`, `:`, or other characters that affect MQTT routing or are rewritten by Emoncms. Do not duplicate these names in the global `[nodes]` section; the ecoMain interfacer preserves the configured logical meter name after standard emonHub receive processing.

## Input Fields

A single-phase logical meter publishes six fields in this fixed order:

1. `power` (W)
2. `energy` (kWh, imported active energy)
3. `return_energy` (kWh, exported active energy)
4. `voltage` (V)
5. `current` (A)
6. `power_factor` (dimensionless)

A three-phase logical meter publishes 15 fields in this fixed order:

1. `power` (W, total across all phases)
2. `energy` (kWh, total imported active energy)
3. `return_energy` (kWh, total exported active energy)
4. `power_l1` (W)
5. `power_l2` (W)
6. `power_l3` (W)
7. `voltage_l1` (V)
8. `voltage_l2` (V)
9. `voltage_l3` (V)
10. `current_l1` (A)
11. `current_l2` (A)
12. `current_l3` (A)
13. `power_factor_l1` (dimensionless)
14. `power_factor_l2` (dimensionless)
15. `power_factor_l3` (dimensionless)

When a branch is configured with `invert = true`, the interfacer negates that phase's `power` and `power_factor` and swaps `energy` with `return_energy`. Voltage and current remain unchanged. For a three-phase branch meter, totals are calculated after applying this transformation to each phase.

## Communication Scope and Limitations

- The driver is read-only. It only reads holding registers using Modbus function code `03` and never writes registers. Register addresses are zero-based.
- The TCP port is fixed at `502`, and the Modbus Unit ID is fixed at `255`; neither is configured in `init_settings`. `host` is the device address, `serial` is the 12-digit serial number printed on the device label (including leading zeroes), and `timeout` is the connection timeout.
- After establishing a TCP connection, the driver validates, in order, that the model is `2401`, the ecoMain software version at address `3009` is at least `139`, and the device serial number exactly matches `serial`. If device information cannot be read or any validation fails, the driver closes the connection, publishes no measurements, and retries using the standard backoff mechanism.
- The driver does not read ecoSub online status. If a branch device read fails, stale values must not be published as new Input data.
- The model, serial number, and hardware/software/firmware versions are written only to the emonHub log and are not published as Inputs.
- This integration does not provide OEM scheduling or control. It does not control EV chargers, heat pumps, or inverters.

After saving the configuration, wait for data to appear on the standard Emoncms `Inputs` page. Configure a process list for each required Input and create or write to the corresponding `Feeds` there. The ecoMain interfacer does not create Feeds automatically.

With the default emonPi/emonBase MQTT configuration, data is published in node-variable format as `emon/<nodename>/<inputname>`. The Emoncms MQTT subscriber uses these topics to create or update Inputs. `nodeid` remains the internal emonHub identifier used for compatibility processing, while the Inputs page groups nodes by `nodename`.
