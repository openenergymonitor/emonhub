### RF69 Interfacer

Read data directly from a RFM69cw module on a RaspberryPi:

```text
    [[SPI]]
        Type = EmonHubRF69Interfacer
        [[[init_settings]]]
            nodeid = 5
            group = 210
            format = 2        # 1 = JeeLib classic, 2 = JeeLib native
            resetPin = 24     # remove line if hardware is emonBase RFM69 SPI
            selPin = 16       # remove line or change to selPin = 26 if hardware is emonBase RFM69 SPI
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
```

### Packet format

`format` selects the packet format, matching the `radio.format()` call of the
[RFM69_JeeLib](https://github.com/openenergymonitor/RFM69_JeeLib) Arduino library
used by the transmitting nodes:

- `format = 1` JeeLib classic, the RFM12B compatible format used by OpenEnergyMonitor
  hardware up to Nov 2022. The RFM69 packet engine is switched off and the frame is
  unpacked and CRC checked in the interfacer.
- `format = 2` JeeLib native (default). The RFM69 packet engine handles the length
  byte, whitening and CRC.

Both formats use the same bit rate, deviation, frequency and sync bytes, but a radio
can only listen for one of them at a time. Neither is the LowPowerLabs format read by
`EmonHubRFM69LPLInterfacer`.

Note that the JeeLib native format can optionally be sent encrypted, this interfacer
does not enable AES and so reads unencrypted packets only.

### Hardware

`selPin` and `resetPin` use BOARD numbering and have the same meaning as in
`EmonHubRFM69LPLInterfacer`, so the same values apply to the same hardware:

| Hardware | selPin | resetPin |
| --- | --- | --- |
| emonPi2 / emonPi3 / emonHP | 16 | 24 |
| emonBase RFM69 SPI | 26 | not wired, omit the line |

The radio is polled rather than driven by the DIO0 interrupt, so the interrupt pin
does not need to be wired or configured. Packets are read at the emonhub loop rate
of 10 times a second, which is ample for nodes transmitting every few seconds, but a
second packet arriving before the first is read will be lost.

If nothing is received for 300 seconds the radio is reset and reconfigured, which
also recovers a radio that failed to start.

Steps to get working:

1. Enable SPI in raspi-config:
2. sudo adduser emonhub spi
3. sudo apt-get install python3-spidev (may just upgrade an existing package)
