### OEM Interfacer

Replaces EmonHubJeeInterfacer with a more flexible implementation that can accept a range of different formats from connected devices, including OpenEnergyMonitor devices. Here are a number of supported data formats: 

- Decimal space seperate representation of RFM binary data e.g OK 5 0 0 0 0 (-0)
- KEY:VALUE format e.g power1:100,power2:200
- JSON format e.g {"power1":100,"power2":200}

Example configuration:

```text
    [[OEM]]
        Type = EmonHubOEMInterfacer
        [[[init_settings]]]
            com_port = /dev/ttyAMA0
            com_baud = 115200
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            
```

```
[[usbdata]]
    Type = EmonHubOEMInterfacer
    [[[init_settings]]]
        com_port = /dev/ttyUSB0
        com_baud = 115200
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        subchannels = ToRFM12,
```
