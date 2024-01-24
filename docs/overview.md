---
github_url: "https://github.com/openenergymonitor/emonhub/blob/master/docs/overview.md"
---
# emonHub Overview

## Introduction

EmonHub is a piece of software running on the emonPi and emonBase that can read/subscribe or send/publish data to and from a multitude of services. It is primarily used as the bridge between the OpenEnergyMonitor monitoring hardware and the Emoncms software but it can also be used to read in data from a number of other sources, providing an easy way to interface with a wider range of sensors.

```{admonition} Troubleshooting?
See common issues and troubleshooting tips here: [Troubleshooting](troubleshooting)
```

---

## Features

The OpenEnergyMonitor variant of emonhub is based on [@pb66 Paul Burnell's](https://github.com/pb66) original adding:

- Internal pub/sub message bus based on pydispatcher
- Publish to MQTT
- Https Emoncms interface
- A multi-file implementation of interfacers.
- Rx and tx modes for node decoding/encoding provides improved control support.
- json based config file option so that emonhub.conf can be loaded by emoncms
- Ongoing development on other interfacers such as the MBUS and Modbus interfacers.

---

## Basic Concept

A number of individual **Interfacers** can be configured within emonHub to collect data from multiple sources and distribute that information to multiple targets, using different protocols.

In its simplest form, emonHub takes data from a Serial Interface and transforms it to a format suitable for emoncms to take as an Input, then sends it to emoncms via HTTP or MQTT.

Each Interfacer communicates by creating *channels*, much like an MQTT Broker, that allows the Interfacer to *Publish* data to a channel and *Subscribe* (get) data from a channel. Each interfacer can communicate over multiple channels.

Each interfacer can listen on a `subchannel` or publish on a `pubchannel`. Some interfacers can do both. An Interfacer needs at least one channel defined of either type.

**For Example:**

The Serial Interfacer listens on a serial port then publishes that data for onward transmission - it has a `pubchannel` defined.

The MQTT interfacer listens for data which it then sends out via MQTT, it therefore defines a `subchannel` that it will listen on for data to send via MQTT.

For data to be passed, the name of the 2 channels must match.

Each Interfacer can have multiple channels defined and multiple interfacers can listen to the same channel. e.g. data published by the Serial Interfacer can be listened (subscribed) for by the MQTT and the HTTP interfacer.

**Note** The channel definition is a list so **must** end with a comma e.g. `pubchannels = ToEmonCMS,` or `pubchannels = ToEmonCMS,ToXYZ,`

---

## Installing Emonhub

### emonScripts

emonHub is installed as standard on the emonSD image built using the EmonScripts install scripts.

### Manual Install

Install emonHub:

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

If the MQTT Interfacer is to be used, Mosquitto needs to be installed.

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

