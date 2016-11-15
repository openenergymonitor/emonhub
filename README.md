## emonHub (emon-pi variant)

Emonhub is typically used in the OpenEnergyMonitor system to first read data received over serial from either the EmonPi board or the RFM12/69Pi adapter board and then second to then forward this data on to emoncms in a decoded ready-to-use form - based on the configuration in [emonhub.conf](https://github.com/openenergymonitor/emonhub/blob/emon-pi/configuration.md)

More generally: Emonhub consists of a series of interfacers that can read/subscribe or send/publish data to and from a multitude of services. EmonHub supports decoding data from:

### Enabled by default

- RFM [JeeLabs data packet structure](http://jeelabs.org/2010/12/07/binary-packet-decoding/) e.g. emonTx, emonTH, JeeNode RFM12 demo etc. 

### Not enabled by default

*See protocol specific readme's in `/conf`*

- Smilics energy monitors (added by @K0den)
- Victron Products e.g  BMV 700 battery monitor (added by @jlark)
- ModBus e.g. FRONIUS Solar inverter (added by @cjthuys)

***

Emonhub is included on the [emonsD pre-built SD card](https://github.com/openenergymonitor/emonpi/wiki/emonSD-pre-built-SD-card-Download-&-Change-Log) used by both the EmonPi and Emonbase. The documentation below convers installing the emon-pi variant of emonhub on linux for self build setups.

### Emon-Pi variant

This variant of emonhub is based on [@pb66 Paul Burnell's](https://github.com/pb66) experimental branch adding: 

- Internal pub/sub message bus based on pydispatcher
- Post to MQTT
- HTTP(S) Emoncms interface
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

Depending on which version of debian your using:

    sudo wget http://repo.mosquitto.org/debian/mosquitto-wheezy.list
    
or: 

    sudo wget http://repo.mosquitto.org/debian/mosquitto-jessie.list

Update apt information:

    sudo apt-get update
    
    sudo apt-get install -y mosquitto python-pip python-serial python-configobj
    sudo pip install paho-mqtt
    sudo pip install pydispatcher
    

It is recommended to turn off mosquitto persistence 

    sudo nano /etc/mosquitto/mosquitto.conf

Set 
    
    persistence false

Install the emon-pi variant of emonhub:

    git clone https://github.com/openenergymonitor/emonhub.git && emonhub/install
    sudo service emonhub start
    
The emonhub configuration guide can be found here:

[emonhub.conf configuration](https://github.com/openenergymonitor/emonhub/blob/emon-pi/configuration.md)

To view the emonhub log via terminal on the emonpi or emonbase:

    tail -f /var/log/emonhub.log
    


### EmonHub Emoncms config module 

If your using Emoncms on the same Raspberry Pi as emonhub you may find the emoncms config module useful which provides in browser access to `emonhub.conf` and `emonhub.log`:

https://github.com/emoncms/config

