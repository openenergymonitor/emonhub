### OEM Interfacer

Replaces EmonHubJeeInterfacer with a more flexible implementation that can accept a range of different formats from connected devices, including:

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
