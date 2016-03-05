#VE Direct interface Victron products#

The VE Direct protocol is as binary/ASCII [protocol](https://www.victronenergy.com/upload/documents/VE.Direct-Protocol.pdf) used by [Victron Energy] to communicate between it's products. For those who don't know, Victron is the leading producer of solar inverters and charge controllers designed for the off grid market.

 With this interfacer now it's possible to interface  data from any VE Direct compatible Victron product with Emon. In this example we use the [BMV 700](https://www.google.rw/url?sa=t&rct=j&q=&esrc=s&source=web&cd=1&cad=rja&uact=8&ved=0ahUKEwi14t-MkqfLAhVBExoKHRGeCioQFggbMAA&url=https%3A%2F%2Fwww.victronenergy.com%2Fbattery-monitors%2Fbmv-700&usg=AFQjCNGENUubkSY_HkWGN61NdkP8onXHag&sig2=XjH6HIbtSzwY_kDDKOfsJw), which is a battery monitor. For emon users that have a battery bank, this will allow them to get stats on their batteries very easily.

##Usage and configuration##
There is a sample vedirect.emonhub.conf file located in this directory.
This is already preconfigured to talk to a BMV700 that is connect to the emonpi via isolated [USB cable](https://www.victronenergy.com/accessories/ve-direct-to-usb-interface)

Each VE Direct product has it's own source of variables that it delivers. The full list of variables can be found on Victron's github page as [datalist.py](https://github.com/victronenergy/velib_python/blob/master/dbusmonitor.py).

This file isn't necessary, but it's just useful as a reference to see which data codes correspond to which values.



###Sample interfacer config within emonhub.conf ###
    # Sample configuration for Victron Product with VEDirect connection over USB
    # Configuration is for BMV 700
    [[VEDirect]]
    Type = EmonHubVEDirectInterfacer
    [[[init_settings]]]
    com_port = /dev/ttyUSB0 # Where to find our device
        com_baud = 19200      # Baud rate needed to decode
        toextract = SOC,CE,TTG,V,I,Relay,Alarm # These are the fields we wish to extract, explanation can be seen in datalist.py
        poll_interval = 10 # How often to get data in seconds
    [[[runtimesettings]]]
        nodeoffset = 9 #make sure this matches with nodename below
        pubchannels = ToEmonCMS,
        subchannels = ToBMV,
        basetopic = emonhub/


### Followed by a  corresponding Node declaration in emonhub.conf###
In this example our battery monitor will be designated node id 9 

    [[9]]
    nodename = emonDC
    firmware =V1_6_emonTxV3_4_DiscreteSampling #not used
    hardware = emonTx_(NodeID_DIP_Switch1:ON) #not used
    [[[rx]]]
       names = SOC,CE,TTG,V,I,Relay,Alarm # Make sure this matches 'toextract' in interfacer
       datacode = 0 #no need to decode values
       scales = 0.1,1,1,0.001,1,1,1 # Some scaling necassary
       units =%,Ah,s,V,A,S,S 


With this config in place now you simply need to restart emonhub on our emonpi by ssh'ing into it and typing 

      $>sudo service emonhub restart

If there are any problems you can debug by looking inside /var/emonhub/emonhub.log

Hope that helps

