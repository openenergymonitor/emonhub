#!/usr/bin/env python3
"""Tests for the cut down RFM69 driver

Runs anywhere, no Raspberry Pi and no radio module needed: spidev and RPi.GPIO
are replaced with fakes that emulate enough of an RFM69 to exercise the driver,
including the failure modes that matter, an unresponsive radio and an SPI error
in the middle of the interrupt handler.

    python3 src/rfm69min/test_radio.py

"""

import os
import signal
import sys
import threading
import time
import types

# Register addresses the fake radio needs to answer for, kept separate from the
# driver's own definitions so the fake does not depend on what it is testing
REG_FIFO = 0x00
REG_OSC1 = 0x0A
REG_RSSIVALUE = 0x24
REG_IRQFLAGS1 = 0x27
REG_IRQFLAGS2 = 0x28
REG_FRFMSB = 0x07
REG_FRFMID = 0x08
REG_FRFLSB = 0x09
REG_TEMP1 = 0x4E
REG_TEMP2 = 0x4F

INT_PIN = 22

# Register writes seen by the fake radio, as (address, value) or (address, [values])
writes = []

# Filled in when one thread asserts chip select while another still holds it,
# which on real hardware means two interleaved SPI transactions
cs_conflicts = []


class FakeSpiDev:
    """Enough of an RFM69 to get the driver through init and a packet receive"""

    def __init__(self):
        self.regs = [0] * 0x100
        self.fifo = []          # bytes the next FIFO read returns
        self.overrides = {}     # address -> value, to simulate a stuck register
        self.fail = False       # raise on every transfer, as a dead SPI bus would
        self.open_error = None  # refuse to open, as a missing device node would
        self.slow = False       # pause mid transfer, to expose threading races
        self.rssi = 180         # REG_RSSIVALUE, 180 reads as -90 dBm
        self.max_speed_hz = None
        self.no_cs = None

    def open(self, bus, device):
        if self.open_error:
            raise OSError(self.open_error)

    def _read(self, addr):
        if addr in self.overrides:
            return self.overrides[addr]
        if addr == REG_IRQFLAGS1:
            return 0x80                                     # MODEREADY
        if addr == REG_IRQFLAGS2:
            return (0x04 if self.fifo else 0x00) | 0x08     # PAYLOADREADY | PACKETSENT
        if addr == REG_OSC1:
            return 0x40                                     # RCCAL_DONE
        if addr == REG_TEMP1:
            return 0x00                                     # measurement complete
        if addr == REG_TEMP2:
            return 150
        if addr == REG_RSSIVALUE:
            return self.rssi
        return self.regs[addr]

    def _transfer_delay(self):
        # Real transfers take microseconds, sleeping here lets the interpreter
        # switch threads mid transaction as it would on hardware
        if self.slow:
            time.sleep(0.0002)

    def xfer(self, data):
        if self.fail:
            raise OSError("SPI transfer failed")
        self._transfer_delay()
        addr = data[0]
        if addr & 0x80:
            self.regs[addr & 0x7F] = data[1]
            writes.append((addr & 0x7F, data[1]))
            return [0] * len(data)
        return [0, self._read(addr & 0x7F)]

    def xfer2(self, data):
        if self.fail:
            raise OSError("SPI transfer failed")
        self._transfer_delay()
        addr = data[0]
        if addr & 0x80:                             # burst write, FIFO or AES key
            writes.append((addr & 0x7F, data[1:]))
            return [0] * len(data)
        if (addr & 0x7F) == REG_FIFO:
            out = [0]
            for _ in range(len(data) - 1):
                out.append(self.fifo.pop(0) if self.fifo else 0)
            return out
        return [0] + [self._read(addr & 0x7F)] * (len(data) - 1)


class FakeGPIO:
    BOARD = 'BOARD'
    IN = 'IN'
    OUT = 'OUT'
    LOW = 0
    HIGH = 1
    RISING = 'RISING'
    callbacks = {}
    cs_owner = None             # thread currently holding chip select low
    edge_detect_error = None    # message to raise from add_event_detect

    @staticmethod
    def setmode(mode):
        pass

    @staticmethod
    def setwarnings(state):
        pass

    @staticmethod
    def setup(pin, mode):
        pass

    @classmethod
    def output(cls, pin, value):
        if pin != BOARD['selPin']:
            return
        if value == cls.LOW:
            owner = cls.cs_owner
            if owner is not None and owner is not threading.current_thread():
                cs_conflicts.append((owner.name, threading.current_thread().name))
            cls.cs_owner = threading.current_thread()
        else:
            cls.cs_owner = None

    @classmethod
    def remove_event_detect(cls, pin):
        cls.callbacks.pop(pin, None)

    @classmethod
    def add_event_detect(cls, pin, edge, callback=None):
        if cls.edge_detect_error:
            raise RuntimeError(cls.edge_detect_error)
        cls.callbacks[pin] = callback

    @staticmethod
    def cleanup():
        pass


spi = FakeSpiDev()

fake_spidev = types.ModuleType('spidev')
fake_spidev.SpiDev = lambda: spi
sys.modules['spidev'] = fake_spidev

fake_rpi = types.ModuleType('RPi')
fake_gpio = types.ModuleType('RPi.GPIO')
for _name in dir(FakeGPIO):
    if not _name.startswith('__'):
        setattr(fake_gpio, _name, getattr(FakeGPIO, _name))
fake_rpi.GPIO = fake_gpio
sys.modules['RPi'] = fake_rpi
sys.modules['RPi.GPIO'] = fake_gpio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfm69min import Radio, InterruptSetupError            # noqa: E402
from rfm69min import radio as radio_module                  # noqa: E402

# How each GPIO library words a failure to watch the DIO0 pin. RPi.GPIO's
# wording is matched on by the interfacer, rpi-lgpio passes through whatever
# lgpio reported, "GPIO busy" for a pin something else already holds.
EDGE_DETECT_ERRORS = ["Failed to add edge detection", "GPIO busy"]

# The settings EmonHubRFM69LPLInterfacer connects with
BOARD = {'isHighPower': False, 'interruptPin': INT_PIN, 'resetPin': None,
         'selPin': 26, 'spiDevice': 0, 'encryptionKey': "89txbe4p8aik5kt3"}


def new_radio(band=43, node_id=5, network_id=210):
    """A radio that has been through the interfacer's connect() sequence"""
    del writes[:]
    spi.fifo = []
    spi.overrides = {}
    spi.fail = False
    radio = Radio(band, node_id, network_id, **BOARD)
    assert radio.init_success, "radio init failed"
    radio.__enter__()
    return radio


def send(payload_length, target_id, sender_id, ctl, data=()):
    """Hand the radio a frame and run its interrupt handler"""
    spi.fifo = [payload_length, target_id, sender_id, ctl] + list(data)
    FakeGPIO.callbacks[INT_PIN](INT_PIN)


def test_init_and_receive():
    radio = new_radio()
    assert INT_PIN in FakeGPIO.callbacks, "interrupt handler not registered"
    assert radio.mode == radio_module.RF69_MODE_RX, "radio not left listening"

    data = [0x0A, 0x01, 0x02, 0x03]
    send(3 + len(data), 5, 19, 0x00, data)
    packet = radio.get_packet()
    assert packet, "no packet received"
    assert packet.sender == 19, packet.sender
    assert packet.receiver == 5, packet.receiver
    assert packet.data == data, packet.data
    assert packet.RSSI == -90, packet.RSSI
    assert radio.get_packet() is False, "queue not emptied"


def test_broadcast_received():
    radio = new_radio()
    send(5, 255, 20, 0x00, [1, 2])
    packet = radio.get_packet()
    assert packet and packet.sender == 20, "broadcast not received"


def test_other_node_ignored():
    radio = new_radio()
    send(7, 7, 19, 0x00, [1, 2, 3, 4])
    assert radio.get_packet() is False, "packet for another node was accepted"


def test_ack_request_answered():
    radio = new_radio()
    send(5, 5, 19, 0x40, [1, 2])                # CTL 0x40 requests an ack
    assert radio.get_packet(), "packet lost while acknowledging"
    frames = [w for w in writes if w[0] == REG_FIFO and isinstance(w[1], list)]
    assert frames, "no ack frame sent"
    # length 3, to node 19, from node 5, CTL 0x80 marks it as an ack
    assert frames[-1][1] == [3, 19, 5, 0x80], frames[-1][1]


def test_incoming_ack_not_data():
    radio = new_radio()
    send(3, 5, 19, 0x80, [])                    # CTL 0x80 is an ack, not data
    assert radio.get_packet() is False, "an ack was delivered as a data packet"


def test_short_frame_discarded():
    """A payload shorter than the 3 byte header is corrupt, not an empty packet"""
    radio = new_radio()
    for payload_length in (0, 1, 2):
        send(payload_length, 5, 19, 0x00, [])
        assert radio.get_packet() is False, \
            "corrupt frame of length %d was delivered" % payload_length


def test_frequency_bands():
    """Each band writes the frequency registers from the RFM69 datasheet"""
    expected = {
        31: (0x4E, 0xC0, 0x00),     # 315MHz
        43: (0x6C, 0x40, 0x00),     # 433MHz
        49: (0x6C, 0x7A, 0xE1),     # 433.92MHz
        86: (0xD9, 0x00, 0x00),     # 868MHz
        91: (0xE4, 0xC0, 0x00),     # 915MHz
    }
    for band, frf in expected.items():
        new_radio(band=band)
        written = tuple(v for a, v in writes
                        if a in (REG_FRFMSB, REG_FRFMID, REG_FRFLSB)
                        and not isinstance(v, list))
        assert written == frf, "band %d wrote %s, expected %s" % (band, written, frf)


def test_polling_mode():
    """With useInterrupts off the reading thread calls the handler itself"""
    FakeGPIO.callbacks.clear()
    radio = Radio(43, 5, 210, useInterrupts=False, **BOARD)
    assert radio.init_success, "radio init failed"
    assert radio.interrupt_enabled is False, "interrupts were set up anyway"
    assert INT_PIN not in FakeGPIO.callbacks, "an interrupt handler was registered"
    radio.__enter__()

    spi.fifo = [7, 5, 21, 0x00, 1, 2, 3, 4]
    radio._interruptHandler(INT_PIN)
    packet = radio.get_packet()
    assert packet and packet.sender == 21, "polling mode did not receive"


def test_edge_detection_failure_is_typed():
    """However the GPIO library words it, the failure must be recognisable

    The interfacer matches RPi.GPIO's wording, so the original message has to
    survive, and catches the type, so other GPIO libraries are covered too.
    """
    for message in EDGE_DETECT_ERRORS:
        FakeGPIO.edge_detect_error = message
        try:
            Radio(43, 5, 210, **BOARD)
        except InterruptSetupError as err:
            assert str(err) == message, "message changed to %r" % str(err)
            assert isinstance(err, RuntimeError), "not a RuntimeError any more"
        except Exception as err:
            raise AssertionError("raised %s instead" % type(err).__name__)
        else:
            raise AssertionError("no error raised for %r" % message)
        finally:
            FakeGPIO.edge_detect_error = None


def test_unresponsive_radio_does_not_block():
    """A radio that stops responding must not block the interfacer thread"""
    radio = new_radio()
    spi.overrides = {REG_TEMP1: 0x04}           # MEAS_RUNNING stuck set
    assert radio.read_temperature() is None, "expected a failed temperature read"
    spi.overrides = {REG_OSC1: 0x00}            # RCCAL_DONE never set
    assert radio.calibrate_radio() is False, "expected a failed calibration"


def test_spi_error_releases_lock():
    """An SPI error in the handler must not wedge the radio"""
    radio = new_radio()
    spi.fifo = [7, 5, 19, 0x00, 1, 2, 3, 4]
    spi.fail = True
    try:
        FakeGPIO.callbacks[INT_PIN](INT_PIN)
    except OSError:
        pass
    spi.fail = False
    assert radio.intLock is False, "intLock left set after an error"
    radio.begin_receive()                       # would block for ever if it were
    send(7, 5, 19, 0x00, [1, 2, 3, 4])
    assert radio.get_packet(), "radio did not recover after an SPI error"


def test_packet_queue_is_bounded():
    radio = new_radio()
    for _ in range(radio_module.MAX_QUEUED_PACKETS + 50):
        send(7, 5, 19, 0x00, [1, 2, 3, 4])
    assert len(radio.packets) == radio_module.MAX_QUEUED_PACKETS, len(radio.packets)


def test_concurrent_access_is_serialised():
    """The interrupt thread and the interfacer thread share the SPI bus

    RPi.GPIO runs the DIO0 callback on its own thread while emonhub's
    interfacer thread is reading packets or restarting the radio. Chip select
    is a separate GPIO write either side of each transfer, so without locking
    the two can interleave and corrupt both transactions.
    """
    radio = new_radio()
    del cs_conflicts[:]
    FakeGPIO.cs_owner = None
    spi.slow = True
    stop = threading.Event()

    def interrupts():
        ctl = 0x00
        while not stop.is_set():
            # alternate plain frames with ones that ask for an acknowledgement,
            # which makes the handler transmit as well as receive
            ctl = 0x40 if ctl == 0x00 else 0x00
            spi.fifo = [7, 5, 19, ctl, 1, 2, 3, 4]
            FakeGPIO.callbacks[INT_PIN](INT_PIN)

    thread = threading.Thread(target=interrupts, name="interrupt")
    thread.start()
    try:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            radio.begin_receive()
            radio.read_temperature()
            radio.get_packet()
    finally:
        stop.set()
        thread.join()
        spi.slow = False

    assert not cs_conflicts, \
        "%d interleaved SPI transactions, first %s" % (len(cs_conflicts), cs_conflicts[0])


def test_shutdown():
    radio = new_radio()
    radio.__exit__()
    assert radio.mode == radio_module.RF69_MODE_SLEEP, "radio not asleep"


# ---------------------------------------------------------------------------
# The interfacer's side of the contract, how it recovers when the radio or the
# GPIO library will not do what it is asked
# ---------------------------------------------------------------------------

def _interfacer(**kwargs):
    """Build the real interfacer against the fake radio"""
    import logging
    log = logging.getLogger("EmonHub")
    log.addHandler(logging.NullHandler())
    log.propagate = False
    from interfacers.EmonHubRFM69LPLInterfacer import EmonHubRFM69LPLInterfacer
    FakeGPIO.callbacks.clear()
    settings = dict(nodeid=5, networkID=210, interruptPin=INT_PIN,
                    selPin=BOARD['selPin'], freqBand=43)
    settings.update(kwargs)
    return EmonHubRFM69LPLInterfacer("RFM69", **settings)


def test_interfacer_falls_back_to_polling():
    """Every GPIO library's wording has to reach the polling fallback"""
    for message in EDGE_DETECT_ERRORS:
        FakeGPIO.edge_detect_error = message
        try:
            interfacer = _interfacer()
        finally:
            FakeGPIO.edge_detect_error = None
        assert interfacer.radio, "no radio after %r" % message
        assert interfacer.radio.init_success, "radio not initialised after %r" % message
        assert interfacer.polling_mode, "polling mode not enabled after %r" % message
        # and it still receives, through the handler the interfacer calls itself
        spi.fifo = [7, 5, 19, 0x00, 1, 2, 3, 4]
        cargo = interfacer.read()
        assert cargo and cargo.nodeid == 19, "no data in polling mode after %r" % message


def test_interfacer_message_match_still_works_on_its_own():
    """RPi.GPIO's wording must keep triggering the fallback by itself

    The exception type was added alongside the message match, not instead of
    it, so the message match has to still work with the type check disabled.
    """
    FakeGPIO.edge_detect_error = "Failed to add edge detection"
    try:
        interfacer = _interfacer()
        interfacer.InterruptSetupError = None       # leave only the message match
        interfacer.polling_mode = False
        interfacer.connect()
    finally:
        FakeGPIO.edge_detect_error = None
    assert interfacer.polling_mode, "the message match no longer reaches the fallback"
    assert interfacer.radio and interfacer.radio.init_success, "radio did not start"


def test_interfacer_survives_a_radio_that_will_not_start():
    """A radio that raises on the way up must not take the interfacer with it

    Anything other than a failed interrupt setup, no SPI device node for
    instance, used to leave self.radio as False and then read its
    init_success, which killed the interfacer with an AttributeError.
    """
    spi.open_error = "No such file or directory"
    try:
        interfacer = _interfacer()
    finally:
        spi.open_error = None
    assert interfacer.radio is False, "expected no radio"
    assert interfacer.read() is False, "expected no data from a radio that never started"


def test_interfacer_watchdog_restarts_a_radio_that_never_receives():
    """The watchdog is armed from connect, not from the first packet"""
    interfacer = _interfacer()
    assert interfacer.radio.init_success
    first = interfacer.radio
    interfacer.read()
    assert interfacer.radio is first, "restarted before the watchdog period"

    interfacer.watchdog_period = -1              # as if the period had elapsed
    interfacer.read()
    assert interfacer.radio is not first, "watchdog did not restart the radio"


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith('test_') and callable(value)]
    failures = 0
    for test in tests:
        # A regression that reintroduces a blocking poll would hang here, so
        # give every test a hard deadline
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(10)
        try:
            test()
        except Exception as err:
            failures += 1
            print("FAIL %-40s %s: %s" % (test.__name__, type(err).__name__, err))
        else:
            print("ok   %s" % test.__name__)
        finally:
            signal.alarm(0)
    print("\n%d tests, %d failures" % (len(tests), failures))
    return 1 if failures else 0


def _timeout(signum, frame):
    raise AssertionError("timed out, the driver is blocking")


if __name__ == '__main__':
    sys.exit(main())
