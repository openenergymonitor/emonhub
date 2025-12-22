Emonhub Modbus RTU Interfacer for E+E sensors 

These are the default modbus setting for these sensors. The Modbus settings can be changed using the PCS10 config utlity (Windows only) 

Pinout sensor cable (195271) HA010832:
- Gray VCC (10-29V DC)
- Green GND 

- Brown Modbys D-
- Yellow Modbus D+

- White N/C 

## EE671 Air Velocity Sensor

https://www.epluse.com/products/air-velocity-instrumentation/air-flow-transmitters-and-probes/ee671

```
    [[EE]]
        Type = EmonHubMinimalModbusInterfacer
        [[[init_settings]]]
            #device = /dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7F002896-if00
            device = /dev/ttyACM*
            baud = 9600
            parity = even
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            read_interval = 10
            nodename = heatpump
            [[[[meters]]]]
                [[[[[EE671]]]]]
                    address = 238
                    byteorder = 3 #Endian.BIG
                    registers = 25,31
                    datatypes = float,float
                    functioncodes = 3,3
                    precision = 1,1
                    names = temperature, velocity
                    units = C, m/s
```

## EE872 Co2, Temperature, Pressure & RH

https://www.epluse.com/products/co2-measurement/co2-modules-and-probes/ee872/

```
    [[EE]]
        Type = EmonHubMinimalModbusInterfacer
        [[[init_settings]]]
            #device = /dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7F002896-if00
            device = /dev/ttyACM*
            baud = 9600
            parity = even
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            read_interval = 10
            nodename = heatpump
            [[[[meters]]]]
                [[[[[EE872]]]]]
                    address = 237
                    byteorder = 3 #Endian.BIG
                    registers = 1002, 1104, 1060, 1062, 1200, 1202, 1020
                    datatypes = float, float, float, float, float, float, float
                    functioncodes = 3,3,3,3,3,3,3
                    precision = 1,1,1,1,1,1,1
                    names = temperature, temperature_dewpoint, co2_avr, co2_raw, pressure_mbar, pressure_psi, RH
                    units = C, C, ppm, ppm, mbar, psi, %                 
```

## Both Together

```
  [[EE]]
        Type = EmonHubMinimalModbusInterfacer
        [[[init_settings]]]
            device = /dev/serial/by-id/usb-1a86_USB_Single_Serial_5A7F002896-if00
            #device = /dev/ttyACM*
            baud = 9600
            parity = even
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            read_interval = 10
            nodename = heatpump
            [[[[meters]]]]
                [[[[[EE872]]]]]
                    address = 237
                    byteorder = 3 #Endian.BIG
                    registers = 1002, 1104, 1060, 1062, 1200, 1202, 1020
                    datatypes = float, float, float, float, float, float, float
                    functioncodes = 3,3,3,3,3,3,3
                    precision = 1,1,1,1,1,1,1
                    names = temperature, temperature_dewpoint, co2_avr, co2_raw, pressure_mbar, pressure_psi, RH
                    units = C, C, ppm, ppm, mbar, psi, %
                [[[[[EE671]]]]]
                    address = 238
                    byteorder = 3 #Endian.BIG
                    registers = 25,31
                    datatypes = float,float
                    functioncodes = 3,3
                    precision = 1,1
                    names = temperature, velocity
                    units = C, m/s
```
