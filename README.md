## emonHub (emon-pi variant)

Emonhub is used in the OpenEnergyMonitor system to read data received over serial from either the EmonPi board or the RFM12/69Pi adapter board then forward the data to emonCMS in a decoded ready-to-use form - based on the configuration in [emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/emon-pi/configuration.md)

More generally: Emonhub consists of a series of interfacers that can read/subscribe or send/publish data to and from a multitude of services. EmonHub supports decoding data from:

### Default Interfacers

- `EmonHubJeeInterfacer`: Decode data received from RFM69Pi & emonPi in [JeeLabs data packet structure](http://jeelabs.org/2010/12/07/binary-packet-decoding/) e.g. emonTx, emonTH, JeeNode RFM12 demo etc.
- `EmonHubMqttInterfacer`: Publish decoded data to MQTT

### Other Interfacers

*See interfacer specific readmes in [/conf/interfacer_examples](conf/interfacer_examples)*

- Direct Serial: space seperated value format
- Direct Serial (emontx3e): current emonTx V3 CSV key:value format (added by @owenduffy)
- Smilics energy monitors (added by @K0den)
- Victron Products e.g  BMV 700 battery monitor (added by @jlark)
- ModBus e.g. FRONIUS Solar inverter (added by @cjthuys)
- Graphite timeseries DB (added by @hmm01i)
- SMASolar (added by @stuartpittaway)
- BMW EV API e.g state of charge, charging state etc. (added by @stuartpittaway)

***

Emonhub is included on the [emonsD pre-built SD card](https://github.com/openenergymonitor/emonpi/wiki/emonSD-pre-built-SD-card-Download-&-Change-Log) used by both the EmonPi and Emonbase. The documentation below covers installing the emon-pi variant of emonhub on linux for self build setups.

### 'Emon-Pi' variant

This variant of emonhub is based on [@pb66 Paul Burnell's](https://github.com/pb66) experimental branch adding:

- Internal pub/sub message bus based on pydispatcher
- Publish to MQTT
- Https Emoncms interface
- A multi-file implementation of interfacers.
- Rx and tx modes for node decoding/encoding provides improved control support.
- json based config file option so that emonhub.conf can be loaded by emoncms

### [emonhub.conf configuration](https://github.com/openenergymonitor/emonhub/blob/emon-pi/configuration.md)

### Installing Emonhub

Emonhub requires the following dependencies:

Mosquitto: (see http://mosquitto.org/2013/01/mosquitto-debian-repository)

    wget http://repo.mosquitto.org/debian/mosquitto-repo.gpg.key
    sudo apt-key add mosquitto-repo.gpg.key
    cd /etc/apt/sources.list.d/

Depending on which version of Debian you're using:

    sudo wget http://repo.mosquitto.org/debian/mosquitto-wheezy.list

or:

    sudo wget http://repo.mosquitto.org/debian/mosquitto-jessie.list

Update apt information:

    sudo apt-get update

    sudo apt-get install -y mosquitto python3-pip python3-serial python3-configobj python3-requests
    sudo pip3 install paho-mqtt

It is recommended to turn off mosquitto persistence

    sudo nano /etc/mosquitto/mosquitto.conf

Set

    persistence false

Install the emon-pi variant of emonhub:

    git clone https://github.com/openenergymonitor/emonhub.git 
    cd emonhub 
    sudo ./install.sh

The emonhub configuration guide can be found here:

[emonhub.conf configuration](https://github.com/openenergymonitor/emonhub/blob/emon-pi/configuration.md)

To view the emonhub log via terminal on the emonpi or emonbase:

    journalctl -f -u emonhub -n 1000


### EmonHub Emoncms config module

If you're using Emoncms on the same Raspberry Pi as emonhub, you may find the emoncms config module useful which provides in-browser access to `emonhub.conf` and `emonhub.log`:

https://github.com/emoncms/config
