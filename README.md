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




## Install

Install the emon-pi variant of emonhub:

    git clone https://github.com/openenergymonitor/emonhub.git && emonhub/install

### Install Dependencies

Thanks to pb66: https://github.com/emonhub/emonhub/issues/134

    wget http://repo.mosquitto.org/debian/mosquitto-repo.gpg.key
    sudo apt-key add mosquitto-repo.gpg.key
    cd /etc/apt/sources.list.d/
    sudo wget http://repo.mosquitto.org/debian/mosquitto-jessie.list
    apt-get update
    
    sudo apt-get install mosquitto python-pip
    sudo pip install paho-mqtt
    sudo pip install pydispatcher
