# Direct Serial emonTx V3 / emonTH

Using emoneESP format direct serial

by @owenduffy

Interfacer for serial output from emonTx V3 (firmware V2.4 and above)

emonTx firmware V2.4+ outputs serial CSV string pairs compatiable with emonESP:

`name:value,name:value`

e.g

`ct1:100,ct2:300` ....

Default baudrate is `115200`


## Config example

Add the following to `emonhub.conf` in the `[interfacers]` section:


```
[interfacers]
### This interfacer manages the EmonTx3 ESP format serial
[[SerialTx3e]]
     Type = EmonHubTx3eInterfacer
      [[[init_settings]]]
           # Un-comment line below if using RS485 adapter
           #com_port = /dev/ttyRS485-0
           # default com port if using USB to UART adapter
           com_port= /dev/ttyUSB0
           com_baud = 115200
      [[[runtimesettings]]]
           #nodeoffset = 1
           # nodeoffet can be used for multiple devices. it will change the nodeID as seen by emonCMS Inputs.
           pubchannels = ToEmonCMS,
```

See [blog post](http://owenduffy.net/blog/?p=9942) by @owenduffy detailing serial connection an emonTx V3 (running stock V2.4+ FW) with RS485 adapter.

