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

