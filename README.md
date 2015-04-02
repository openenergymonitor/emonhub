emonHub
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

Assuming that you have already got emonhub installed via the easy installer here https://github.com/emonhub/dev-emonhub

    git clone https://github.com/emonhub/dev-emonhub.git ~/dev-emonhub && ~/dev-emonhub/install

To switch to this branch (installed alongside existing emonhub branch):

    git clone https://github.com/trystanlea/emonhub.git hub
    
Change emonhub /etc/default/emonhub

    sudo nano /etc/default/emonhub

to: 

    ## emonHub settings
    
    # Edit this to configure the parameters used in
    # the /etc/init.d/emonhub script.
    
    # This file should be deployed to /etc/default/emonhub
    # unless you have edited the init.d file to give an
    # alternate SYSCONF_PATH
    
    # Specify the directory in which emonhub.py is found:
    EMONHUB_PATH=/home/pi/hub/src/
    
    # Specify the full config file path:
    EMONHUB_CONFIG=/home/pi/hub/conf/emonhub.json
    
    # Specify the full log file path:
    EMONHUB_LOG=/var/log/emonhub/emonhub.log

Edit configuration in /home/pi/hub/conf/emonhub.json

    nano /home/pi/hub/conf/emonhub.json

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
