# Interfacer for Victron VE.Direct Protocol

The VE.Direct protocol is as binary/ASCII [protocol](https://www.victronenergy.com/live/vedirect_protocol:faq) created and used by [Victron Energy](https://www.victronenergy.com/) for communication between and with their products.

This interfacer provides support for reading data from any Victron product that can use the VE.Direct protocol for inter-device communication. Currently this includes the BMV600, BMV700, Blue Solar MPPT, and Phoenix ranges. 

Example configurations are provided for the BMV700 battery monitor and Blue Solar MPPT charge controller.

A VE.Direct to USB converter is available from Victron which would allow direct connection to a emonPi/Raspberry Pi or laptop.

## Usage and configuration

Each supported product has it's own set of data that can be read over VE.Direct called 'fields' . The full list of available fields can be found in the VE.Direct Protocol white paper found [here](https://www.victronenergy.com/support-and-downloads/whitepapers). This information can be used to adapt the provided configurations for your device.

### Sample interfacer config for a BMV700
    # Sample configuration for Victron Product with VEDirect connection over USB
    # Configuration is for BMV 700
    [[VEDirect]]
    Type = EmonHubVEDirectInterfacer
        [[[init_settings]]]
            com_port = /dev/ttyUSB0 # Where to find our device
            com_baud = 19200      # Baud rate needed to decode
            toextract = SOC,CE,TTG,V,I,Relay,Alarm 
            poll_interval = 10 # How often to get data in seconds
        [[[runtimesettings]]]
            nodeoffset = 9 #make sure this matches with nodename below
            pubchannels = ToEmonCMS,
            subchannels = ToBMV,
            basetopic = emonhub/


    # Followed by a  corresponding Node declaration 

    [[9]] # This node name should be consistent with the nodeoffset parameter above
        nodename = VictronBMV700
    [[[rx]]]
       names = SOC,CE,TTG,V,I,Relay,Alarm # Make sure this matches 'toextract' in interfacer definition above
       datacode = 0 #no need to decode values
       scales = 0.1,1,1,0.001,1,1,1 # Some scaling necassary
       units = %,Ah,s,V,A,S,S 


With this config in place you just need to restart emonhub on your emonPi by rebooting it or ssh'ing into it and typing 

      $>sudo service emonhub restart

If there are any problems you can debug by looking inside /var/emonhub/emonhub.log.
