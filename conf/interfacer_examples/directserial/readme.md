Emonhub can read from a serial device directly e.g. `/dev/ttyUSB0`

## Data Format

Data should be printed to serial (integer only) with space sperators in the format:

`NODEID VAR1 VAR2 VAR3` ....and so on

Here is an example of printing data from an Arduino sketch:


```
Serial.print(nodeID);     Serial.print(' ');
Serial.print((int)(realPower1)); Serial.print(' ');   // These for compatibility, but whatever you need if emonHub is configured to suit.
Serial.print((int)(realPower2)); Serial.print(' ');
Serial.print((int)(realPower3)); Serial.print(' ');
Serial.print((int)(realPower4)); Serial.print(' ');
Serial.print((int)(Vrms*100));
```

## Example emonhub Config

In the `[interfacers]` section:

```
[[SerialDirect]]
     Type = EmonHubSerialInterfacer
      [[[init_settings]]]
           com_port = /dev/ttyUSB0
           com_baud = 9600
      [[[runtimesettings]]]
           pubchannels = ToEmonCMS,
```

## Debugging

- Ensure the data received on the serial port is 100% numerical characters with no rogue spaces. Non-numerical characters could result in `Thread is dead` error.