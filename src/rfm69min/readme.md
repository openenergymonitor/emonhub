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

Changes on top of upstream, beyond the cut down:

- every register poll has a timeout (`REG_POLL_TIMEOUT_S`) so an unresponsive
  radio cannot block the interfacer thread forever
- the interrupt handler always releases `intLock` and returns to receive, even
  if an SPI transfer raises, so a single error cannot wedge the radio
- frames claiming a payload shorter than the 3 byte header are discarded rather
  than delivered as empty packets
- the received packet queue is bounded (`MAX_QUEUED_PACKETS`, oldest dropped)
- timeouts use `time.monotonic`, as a Pi without an RTC steps its wall clock at
  boot
- `send_ack` gives up after `RF69_CSMA_LIMIT_S` if the channel stays busy
- SPI access is serialised with a lock, as the DIO0 interrupt handler runs on
  its own thread alongside the interfacer thread

Tests: `python3 src/rfm69min/test_radio.py`, which replaces spidev and RPi.GPIO
with fakes so it runs anywhere, no Raspberry Pi and no radio module needed.

Licence: GPL v3 (rpi-rfm69), register definitions GPL v2 or later (LowPowerLabs).
