emonhub interfacer for EE671 Air Velocity Sensor 
https://www.epluse.com/products/air-velocity-instrumentation/air-flow-transmitters-and-probes/ee671

These are the default modbus setting for this sensor. The Modbus settings can be changed using the EE (PCS10) Config Utlity 

Pinout sensor cable (195271) HA010832:
- Gray VCC (10-29V DC)
- Green GND 

- Brown Modbys D-
- Yellow Modbus D+

- White N/C 

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
                    precision = 1,1electric 
                    names = temperature, velocity
                    units = C, m/s
```
