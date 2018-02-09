Emonhub can read from a serial device directly e.g. `/dev/ttyUSB0`

## Data Format

Data should be printed to serial (integer only) with space sperators in the format:

`NODEID VAR1 VAR2 VAR3` ....and so on

Here is an example of printing data from an Arduino sketch:


```
Serial.print(nodeID);     Serial.print(' ');
Serial.print(realPower1); Serial.print(' ');
Serial.print(realPower2); Serial.print(' ');
Serial.print(realPower3); Serial.print(' ');
Serial.print(realPower4); Serial.print(' ');
Serial.print(Vrms); Serial.println();
```

## Example emonhub Config

In the `[interfacers]` section:

```
[[SerialDirect]]
     Type = EmonHubSerialInterfacer
      [[[init_settings]]]
           com_port = /dev/ttyUSB0      # or /dev/ttyAMA0 or/dev/ttyACM0 etc
           com_baud = 9600              # to match the baud of the connected device
      [[[runtimesettings]]]
           pubchannels = ToEmonCMS,
```
In the `[nodes]` section:

```
[[99]]
    nodename = my-serial-device
    [[[rx]]]
       names = power1, power2, power3, power4, vrms
       datacode = 0      # not essential as "0" is default datacode for serial interfacer
       scale = 1         # not essential as "1" is default scale for serial interfacer
       units =W,W,W,W,V
```
## Debugging

- Ensure the data received on the serial port is 100% numerical characters with no rogue spaces. Non-numerical characters could result in `Thread is dead` error.
