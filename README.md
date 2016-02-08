## emonHub (emon-pi variant)

Emonhub is typically used in the OpenEnergyMonitor system to first read data received over serial from either the EmonPi board or the RFM12/69Pi adapter board and then second to then forward this data on to emoncms in a decoded ready-to-use form.

More generally: Emonhub consists of a series of interfacers that can read/subscribe or send/publish data to and from a multitude of services.

Emonhub is included on the pre-built SD card used by both the EmonPi and Emonbase. The documentation below convers installing the emon-pi variant of emonhub on linux for self build setups.

### Emon-Pi variant

This variant of emonhub is based on [@pb66 Paul Burnell's](https://github.com/pb66) experimental branch adding: 

- Internal pub/sub message bus based on pydispatcher
- Tested MQTT interfacer (integrated with new emoncms nodes module)
- HTTP Emoncms interfacer (rather than reporter). 
- Reporters have been removed. 
- A multi-file implementation of interfacers.
- Rx and tx modes for node decoding/encoding provides improved control support.
- json based config file option so that emonhub.conf can be loaded by emoncms - intention is to provide config interface in emoncms.

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

### EmonHub Emoncms config module 

If your using emoncms on the same raspberry pi as emonhub you may find the emoncms config module useful which provides in browser access to emonhub.conf and emonhub.log:

https://github.com/emoncms/config

