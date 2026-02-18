### Plum ecoNET 300

This interfacer polls a Plum ecoNET 300 bridge (as used by some Grant Aerona HP290 heat pumps) to retrieve telemetry and expose it to emonhub channels.

Only Grant Aerona R290 heat pumps are supported at present; the interfacer assumes that the connected bridge is an ecoNET 300.

Example configuration:

    [[Econet300HTTP]]
        Type = EmonHubEconet300Interfacer

        [[[init_settings]]]
            # Hostname or IP address of the ecoNET 300 bridge
            host = 192.168.1.100
            # HTTP basic auth credentials for the ecoNET 300 bridge
            username = admin
            password = admin
            # Poll interval in seconds (time between successful polls)
            pollinterval = 60
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
