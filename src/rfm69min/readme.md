# rfm69min

Minimal RFM69 radio driver used by `EmonHubRFM69LPLInterfacer` to receive
LowPowerLabs format packets from an RFM69 module on the Raspberry Pi SPI bus.

Cut down from [openenergymonitor/rpi-rfm69](https://github.com/openenergymonitor/rpi-rfm69)
v0.3.7 (tag `v0.3.0-oem-7`), which is a fork of
[jgillula/rpi-rfm69](https://github.com/jgillula/rpi-rfm69), itself a port of the
[LowPowerLabs RFM69](https://github.com/LowPowerLab/RFM69) Arduino library by
Felix Rusu. Included here rather than pip installed as emonhub is the only user of it. The
package is named `rfm69min` to distinguish this minimal copy from the `RFM69`
package the pip installed library provides.

Kept: radio init and configuration, receive via the DIO0 interrupt (or by
calling `_interruptHandler` directly when polling), acknowledgement of packets
that request it, and shutdown.

Removed: transmit (other than acknowledgements), listen mode, asyncio support,
the console logger, register dumps and every register definition not used by
what is left. See the upstream repository for those.

Licence: GPL v3 (rpi-rfm69), register definitions GPL v2 or later (LowPowerLabs).
