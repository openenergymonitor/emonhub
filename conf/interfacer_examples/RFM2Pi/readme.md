### [[RFM2Pi]]

The `[[RFM2Pi]]` interfacer section contains the settings to read from RFM69Pi / emonPi boards via GPIO internal serial port `/dev/ttyAMA0`. The default serial baud on all emonPi and RFM69Pi is `38400`. Older RFM12Pi boards using `9600` baud.

The frequency and network group must match the hardware and other nodes on the network.

The `calibration` config is used to set the calibration of the emonPi when using USA AC-AC adapters 110V. Set `calibration = 110V` when using USA AC-AC adapter.

```text
[[RFM2Pi]]
    Type = EmonHubJeeInterfacer
    [[[init_settings]]]
        com_port = /dev/ttyAMA0
        com_baud = 38400                        # 9600 for old RFM12Pi
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        subchannels = ToRFM12,

        group = 210
        frequency = 433
        baseid = 5                              # emonPi / emonBase nodeID
        quiet = true                            # Report incomplete RF packets (not implemented on emonPi)
        calibration = 230V                      # (UK/EU: 230V, US: 110V)
        # interval =  0                         # Interval to transmit time to emonGLCD (seconds)
```
