ConWinTop have a range of environmental sensors with Modbus RS485 output

# Temperature & Humidity Duct Mount 

[https://store.comwintop.com/products/pipeline-air-duct-type-temperature-and-humidity-transmitter-with-rs485-4-20ma-0-5v-0-10v-output?variant=45497582780643](https://store.comwintop.com/products/pipeline-air-duct-type-temperature-and-humidity-transmitter-with-rs485-4-20ma-0-5v-0-10v-output?variant=45497582780643)

- Test unit: CWT-ADTH-S
- Temperature accuracy ± 0.3 ° C, humidity accuracy ± 3% RH, high precision, low drift;

On the test unit with both DIP switches in the OFF position the default the **default address was 4**:

*ADTH = Air, Duct, Temperature & Humidity *

```
[[ConWinTop]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyACM0
        baud = 4800
        parity = none
        datatype = int
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = CWT
        [[[[meters]]]]
            [[[[[ADTH]]]]]
                address = 4
                registers = 0, 1
                names = humidity, temperature
                scales = 0.1, 0.1
                precision = 1, 1
```

# Air Flow Duct Mount 

[https://store.comwintop.com/products/rs485-4-20ma-0-5v-0-10v-pipeline-duct-type-air-volume-and-air-speed-sensor-airflow-air-velocity-transmitter?variant=45471071273187](https://store.comwintop.com/products/rs485-4-20ma-0-5v-0-10v-pipeline-duct-type-air-volume-and-air-speed-sensor-airflow-air-velocity-transmitter?variant=45471071273187)

- Test unit: CWT-DTAS-10-S (10ms) : (Duct Type Air Sensor)
- The accuracy of the range 0~10m/s is ±(0.1+2%FS); the accuracy of the range 0~15m/s, 0~20m/s, and
0~30m/s is ±(0.2+2%FS) m/s

```
[[ConWinTop]]
    Type = EmonHubMinimalModbusInterfacer
    [[[init_settings]]]
        device = /dev/ttyACM0
        baud = 4800
        parity = none
        datatype = int
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        nodename = CWT
        [[[[meters]]]]
            [[[[[ADTH]]]]]
                address = 4
                registers = 0, 1
                names = velocity, volume,     
                scales = 0.1, 0.1
                precision = 1, 1
```

There is a python script in this repo to set the duct width and the modbus address
