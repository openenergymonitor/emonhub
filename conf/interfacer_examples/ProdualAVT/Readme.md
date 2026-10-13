Produal AVT (Air Velocity Transmitter)

AVT air velocity transmitters measure air velocity and temperature in ventilation ducts. They are commonly used in HVAC/R systems for in-duct temperature monitoring, in-duct air flow and velocity monitoring, and VAV applications. The transmitters have separate readings and outputs for air velocity and temperature.

https://www.produal.com/uk/avt.html

[Datasheet](https://produal-pim.rockon.io/rockon/api/v1/int/extmedia/openFile/01TGWJBKH64E3OCDURBRHJ6HF2XCUL7UGK)

[Modbus Referance](https://produal-pim.rockon.io/rockon/api/v1/int/extmedia/openFile/01TGWJBKCNOIBV7WD7URG2S6KNWZVL7APT)


```
 [[AVT]]
        Type = EmonHubMinimalModbusInterfacer
        [[[init_settings]]]
            #device = /dev/serial/by-id/xxxxxx
            device = /dev/ttyACM*
            baud = 19200
            datatype = int
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            read_interval = 10
            nodename = produal
            [[[[meters]]]]
                [[[[[avt]]]]]
                    address = 1
                    registers = 0, 2
                    names = velocity_ms, temperature_c
                    datacodes = H, h
                    scales = 0.01, 0.1
                    precision = 2, 1
                    functioncodes = 4,4 # Read Input registers 
```


