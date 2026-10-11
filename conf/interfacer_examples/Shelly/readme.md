### Shelly Gen2+ (Pro, Plus, Gen3, Gen4)

Reads power, energy, voltage, current and output state from Shelly Gen2 and later
devices on the local network, using their RPC API. Tested with the Pro 3EM, Pro 1PM,
Pro 2PM and Pro Dimmer 0/1-10V PM. Any device with `switch`, `light`, `cover`, `pm1`,
`em`/`emdata` or `em1`/`em1data` components should work. Gen1 devices (Shelly 1, Shelly
EM, the original Shelly 3EM) use a different protocol and are not supported.

Each device keeps one websocket open to the Shelly, which pushes changes as they
happen and its meter readings at least once a minute, and the interfacer publishes
the latest values every `read_interval` seconds. This needs the `websocket-client`
module (`sudo apt install python3-websocket`); without it the interfacer polls each
device over HTTP instead. A device can also be set to `transport = http`. Polled values
are published at the next interval, stamped with the time they were read.

A Shelly accepts a limited number of simultaneous RPC connections (6). The interfacer
uses one per device, alongside anything else connected to it, such as a Victron GX or
Home Assistant.

```text
[[Shelly]]
    Type = EmonHubShellyInterfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        [[[[devices]]]]
            [[[[[heatpump]]]]]
                host = shellypro3em-aabbccddeeff.local
                fields = a_power, a_energy, a_voltage, a_current, a_pf
            [[[[[immersion]]]]]
                host = shellypro2pm-aabbccddeeff.local
```

Each device becomes an emoncms node with the name of its section.

| Device setting | |
|---|---|
| `host` | IP address or hostname. Gen2+ devices answer mDNS as `<device id>.local`, e.g. `shellypro2pm-aabbccddeeff.local`; the device id is on the device's web page under Settings → Device information |
| `fields` | Inputs to publish, in this order. A name the device does not report is logged once. Optional |
| `password` | The device password, if authentication is enabled on it. Optional |
| `transport` | `ws` (default) or `http`. Optional |

#### Inputs

Inputs are named `<component><id>_<field>`, e.g. `switch0_power`, `switch1_energy`,
`light0_brightness`. A component type ending in a digit gets an underscore before its
id: `em1_0_power`, `pm1_0_energy`. A Pro 3EM in the triphase profile gives `a_power`,
`b_energy`, `total_power` and so on, with no prefix.

By default every value of these kinds is published:

| Field | Unit | |
|---|---|---|
| `power` | W | Active power. Signed on the Pro 3EM and Pro EM |
| `energy` | Wh | Lifetime energy counter |
| `voltage` | V | |
| `current` | A | |
| `pf` | | Power factor |
| `output` | 0/1 | Relay or light on |
| `brightness` | % | Dimmers |

These can be named in `fields`: `freq` (Hz), `ret_energy` (Wh returned),
`apparent_power` (VA), `temperature` (°C, the device's internal temperature),
`position` (%, covers), `n_current` (A, Pro 3EM neutral), `total_apparent_power`,
`total_ret_energy`.

#### Energy

`energy` is the device's own counter, which survives a reboot. Log it in emoncms with
the **Wh Accumulator** process, which carries the total across a counter reset. A
Shelly reports 0 for a moment while booting; a counter reading exactly 0 is not
published.

A quiet device's last values stand while its websocket is up. When the socket drops
(no ping reply within 15 s), or an HTTP poll fails, the device publishes nothing, so
emoncms shows a gap rather than a stale value.

#### Credits

Status merging and digest authentication follow
[aioshelly](https://github.com/home-assistant-libs/aioshelly) (Apache 2.0). The field
mapping and the zero energy counter rule follow Victron's
[dbus-shelly](https://github.com/victronenergy/dbus-shelly) (MIT).
