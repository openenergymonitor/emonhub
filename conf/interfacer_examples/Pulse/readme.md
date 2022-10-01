### Direct Pulse counting

This EmonHub interfacer can be used to read directly from pulse counter connected to a GPIO pin on the RaspberryPi.

- **pulse_pin:** Pi GPIO pin number must be specified. Create a second interfacer for more than one pulse sensor
- **Rate_limit:** The rate in seconds at which the interfacer will pass data to emonhub for sending on. Too short and pulses will be missed. Pulses are accumulated in this period.
- **nodeoffset:** Default NodeID is 0. Use nodeoffset to set NodeID

Example Pulse counting EmonHub configuration:

    [[pulse]]
        Type = EmonHubPulseCounterInterfacer
        [[[init_settings]]]
            pulse_pin = 15
            # bouncetime = 2
            # rate_limit = 2
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            nodeoffset = 3

