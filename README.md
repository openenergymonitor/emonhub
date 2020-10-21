# emonHub

emonHub is used in the OpenEnergyMonitor system to read data received over serial from either the EmonPi board or the RFM12/69Pi adapter board then forward the data to emonCMS in a decoded ready-to-use form - based on the configuration in [emonhub.conf](conf/emonhub.conf)

More generally: Emonhub consists of a series of interfacers that can read/subscribe or send/publish data to and from a multitude of services. EmonHub supports decoding data from:

Emonhub is included on the [emonsD pre-built SD card](https://github.com/openenergymonitor/emonpi/wiki/emonSD-pre-built-SD-card-Download-&-Change-Log) used by both the EmonPi and Emonbase. The documentation below covers installing the emon-pi variant of emonhub on linux for self build setups.

## Features

This vesrion of emonhub is based on [@pb66 Paul Burnell's](https://github.com/pb66) original adding:

- Internal pub/sub message bus based on pydispatcher
- Publish to MQTT
- Https Emoncms interface
- A multi-file implementation of interfacers.
- Rx and tx modes for node decoding/encoding provides improved control support.
- json based config file option so that emonhub.conf can be loaded by emoncms

## Interfacers

### Default Interfacers

- `EmonHubJeeInterfacer`: Decode data received from RFM69Pi & emonPi in [JeeLabs data packet structure](http://jeelabs.org/2010/12/07/binary-packet-decoding/) e.g. emonTx, emonTH, JeeNode RFM12 demo etc.
- `EmonHubMqttInterfacer`: Publish decoded data to MQTT in a format compatible with emonCMS.

### Other Interfacers

*See interfacer specific readmes in [/conf/interfacer_examples](conf/interfacer_examples)*

- Direct Serial: space seperated value format
- Direct Serial (EmonHubTx3eInterfacer): current emonTx V3 CSV key:value format (added by @owenduffy)
- Smilics energy monitors (added by @K0den)
- Victron Products e.g  BMV 700 battery monitor (added by @jlark)
- ModBus e.g. FRONIUS Solar inverter (added by @cjthuys)
- Graphite timeseries DB (added by @hmm01i)
- SMASolar (added by @stuartpittaway)
- BMW EV API e.g state of charge, charging state etc. (added by @stuartpittaway)

***
## Installing Emonhub

### emonScripts

It can be installed by making suitable modifications to the emonScripts script.

### Manual Install

Emonhub requires Mosquitto

```bash
sudo apt-get update
sudo apt-get install -y mosquitto
```

It is recommended to turn off mosquitto persistence

```bash
sudo nano /etc/mosquitto/mosquitto.conf
```

Set

```text
persistence false
```

Install emonhub:

```bash
git clone https://github.com/openenergymonitor/emonhub.git
cd emonhub
git checkout stable
sudo ./install.sh
```

To view the emonhub log via terminal on the emonpi or emonbase:

```bash
journalctl -f -u emonhub
```

## Configuration

The emonhub configuration guide can be found here:

[emonhub.conf configuration](configuration.md)

## EmonHub Emoncms config module

The emonhub config module is now included on the standard emoncms build.  If you're using Emoncms on the same Raspberry Pi as emonhub, the emoncms config module provides in-browser access to `emonhub.conf` and `emonhub.log`
