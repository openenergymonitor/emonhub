#Smilics interface#

This interface starts a http server and listens for GET requests from Smilics products like the Wibeee

##Usage and configuration##
There is a sample smilics.emonhub.conf file located in this directory.
This is preconfigured to listen on port 8080

###Sample interfacer config within emonhub.conf ###
    # Sample configuration for Smilics products
    [[SMILICS_INTERFACE]]
        Type = EmonHubSmilicsInterfacer
        [[[init_settings]]]
            port = 8080
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS
            subchannels = ToSmilics


### Sample Node declaration in emonhub.conf###
Using the Wibeee mac-address, without colons, as node id.

    [[121111111111]]
        nodename = SMILICS01
        firmware =V120
        hardware = Smilics Wibeee
        [[[rx]]]
           names = power1, power2, power3, power_total, wh1, wh2, wh3, wh_total
           datacodes = h, h, h, h, h, h, h, h
           scales       = 1, 1, 1, 1, 1, 1, 1, 1
           units = W, W, W, W, Wh, Wh, Wh, Wh


With this config in place, you simply need to restart emonhub on our emonpi by ssh'ing into it and typing 

      $>sudo service emonhub restart
