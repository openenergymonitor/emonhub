emonHub (emon-pi variant)
=======
This variant of emonhub is based on [@pb66 Paul Burnell's](https://github.com/pb66) experimental branch adding: 

- Internal pub/sub message bus based on pydispatcher
- Tested MQTT interfacer (integrated with new emoncms nodes module)
- HTTP Emoncms interfacer (rather than reporter). 
- Reporters have been removed. 
- A multi-file implementation of interfacers.
- Rx and tx modes for node decoding/encoding provides improved control support.
- json based config file option so that emonhub.conf can be loaded by emoncms - intention is to provide config interface in emoncms.

(emonhub.conf configuration](https://github.com/openenergymonitor/emonhub/blob/emon-pi/configuration.md)

## Install Dependencies

Thanks to pb66: https://github.com/emonhub/emonhub/issues/134

    wget http://repo.mosquitto.org/debian/mosquitto-repo.gpg.key
    sudo apt-key add mosquitto-repo.gpg.key
    cd /etc/apt/sources.list.d/
    sudo wget http://repo.mosquitto.org/debian/mosquitto-jessie.list
    apt-get update
    
    sudo apt-get install -y python-serial python-configobj mosquitto python-pip
    sudo pip install paho-mqtt
    sudo pip install pydispatcher
    

Recommended to turn off mosquitto persistence 

    sudo nano /etc/mosquitto/mosquitto.conf

Set 
    
    persistence false

## Install

Install the emon-pi variant of emonhub:

    git clone https://github.com/openenergymonitor/emonhub.git && emonhub/install
    sudo service emonhub start

## Install EmonHub Emoncms config module 

(optional)

https://github.com/emoncms/config

