"""Tests for EmonHubMBUSInterfacer.

Run from the repository root:  python3 -m unittest discover tests

The Kamstrup Multical 402 frame is built from the RSP_UD layout in Kamstrup's
"M-Bus modules for MULTICAL 402" technical description (5512-820, section 6.1),
with values taken from a real meter's decoded output.
"""

import os
import struct
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "src", "interfacers"))

import EmonHubMBUSInterfacer as mbus  # noqa: E402


def data_record(head, value, length=4):
    """A data record: DIF/DIFE/VIF bytes followed by a little-endian integer."""
    return bytes(head) + value.to_bytes(length, "little")


def kamstrup402_frame(in_b_vif=0x14):
    """in_b_vif: 0x14 when pulse input B counts volume (0.01 m3), 0x06 when it counts kWh."""
    body = bytes([0x08, 0x01, 0x72,            # C, A, CI
                  0x23, 0x97, 0x12, 0x61,      # ID
                  0x2D, 0x2C, 0x0B, 0x04,      # KAM, version 11, heat
                  0x01, 0x00, 0x00, 0x00])     # access, status, signature
    body += bytes([0x0C, 0x78, 0x23, 0x97, 0x12, 0x61])  # 1 fabrication no. (BCD)
    body += data_record([0x04, 0x06], 293495)          # 2 E1, kWh
    body += data_record([0x04, 0x14], 6490563)         # 3 V1, 0.01 m3
    body += data_record([0x04, 0x22], 70888)           # 4 hour counter
    body += data_record([0x04, 0x59], 4791)            # 5 T1, 0.01 C
    body += data_record([0x04, 0x5D], 4459)            # 6 T2
    body += data_record([0x04, 0x61], 332)             # 7 T1-T2
    body += data_record([0x04, 0x2D], 57)              # 8 power, 0.1 kW
    body += data_record([0x14, 0x2D], 236)             # 9 peak power
    body += data_record([0x04, 0x3B], 1485)            # 10 flow, l/h
    body += data_record([0x14, 0x3B], 1616)            # 11 peak flow
    body += data_record([0x84, 0x10, 0x06], 0)         # 12 TA2
    body += data_record([0x84, 0x20, 0x06], 0)         # 13 TA3
    body += data_record([0x84, 0x40, 0x14], 0)         # 14 In-A
    body += data_record([0x84, 0x80, 0x40, in_b_vif], 0)  # 15 In-B
    body += data_record([0x84, 0xC0, 0x40, 0x06], 240) # 16 E3 cooling
    body += data_record([0x04, 0x6D], 683945229)       # 17 date/time
    body += data_record([0x44, 0x06], 277265)          # 18.. target data
    body += data_record([0x44, 0x14], 5983059)
    body += data_record([0x54, 0x2D], 417)
    body += data_record([0x54, 0x3B], 2141)
    body += data_record([0xC4, 0x10, 0x06], 0)
    body += data_record([0xC4, 0x20, 0x06], 0)
    body += data_record([0xC4, 0x40, 0x14], 0)
    body += data_record([0xC4, 0x80, 0x40, in_b_vif], 0)
    body += data_record([0xC4, 0xC0, 0x40, 0x06], 230)
    body += bytes([0x42, 0x6C, 0xBF, 0x2C])    # 27 target date
    body += bytes([0x0F]) + bytes(57)          # manufacturer data
    assert len(body) == 0xF7
    return bytes([0x68, len(body), len(body), 0x68]) + body + bytes([sum(body) % 256, 0x16])


class FakeSerial:
    def __init__(self, data):
        self.data = bytearray(data)

    @property
    def in_waiting(self):
        return len(self.data)

    def read(self, n):
        out, self.data = self.data[:n], self.data[n:]
        return bytes(out)


def make_interfacer():
    with mock.patch.object(mbus.EmonHubMBUSInterfacer, "connect"):
        iface = mbus.EmonHubMBUSInterfacer("MBUS")
    iface.set()  # apply the interfacer's default settings
    return iface


class Kamstrup402Test(unittest.TestCase):

    def test_full_frame_record_names(self):
        result = make_interfacer().parse_frame(list(kamstrup402_frame()), [])
        self.assertEqual(len(result), 28)  # 27 records + heat_calc
        self.assertEqual(result["Energy4"], [240, "kWh"])
        self.assertEqual(result["Energy5"], [277265, "kWh"])

    def test_preset_records(self):
        result = make_interfacer().parse_frame(list(kamstrup402_frame()), [2, 3, 5, 6, 7, 8, 10, 16])
        self.assertEqual(set(result), {"Energy", "Volume", "FlowT", "ReturnT", "DeltaT",
                                       "Power", "FlowRate", "Energy4", "heat_calc"})
        self.assertEqual(result["Energy"], [293495, "kWh"])
        self.assertAlmostEqual(result["Volume"][0], 64905.63)
        self.assertAlmostEqual(result["FlowT"][0], 47.91)
        self.assertEqual(result["Power"], [5700, "W"])
        self.assertAlmostEqual(result["FlowRate"][0], 1.485)

    def read_preset(self, frame):
        iface = make_interfacer()
        iface._settings.update(read_interval=30,
                               meters={"heatmeter": {"address": 1, "type": "kamstrup402"}})
        iface.ser = FakeSerial(b"")
        iface.mbus_serial_write = lambda data: iface.ser.data.extend(frame)
        with mock.patch.object(mbus.time, "time", return_value=1800.0), \
             mock.patch.object(mbus.time, "sleep"):
            cargo = iface.read()
        return dict(zip(cargo.names, cargo.realdata))

    def test_read_uses_preset_names(self):
        values = self.read_preset(kamstrup402_frame())
        self.assertEqual(set(values), {"heatmeter_" + n for n in [
            "Energy", "Volume", "Hours", "FlowT", "ReturnT", "DeltaT",
            "Power", "FlowRate", "Cooling", "heat_calc"]})
        self.assertEqual(values["heatmeter_Energy"], 293495)
        self.assertEqual(values["heatmeter_Hours"], 70888)
        self.assertEqual(values["heatmeter_Cooling"], 240)

    def test_cooling_with_energy_pulse_input(self):
        # An energy pulse input shifts the generated names: E3 decodes as Energy5, not Energy4
        frame = kamstrup402_frame(in_b_vif=0x06)
        self.assertEqual(make_interfacer().parse_frame(list(frame), [])["Energy5"], [240, "kWh"])
        self.assertEqual(self.read_preset(frame)["heatmeter_Cooling"], 240)


class ReadDataFrameTest(unittest.TestCase):

    def test_valid_frame_resets_invalid_count(self):
        iface = make_interfacer()
        iface.invalid_count = 5
        iface.ser = FakeSerial(kamstrup402_frame())
        self.assertIsNotNone(iface.read_data_frame([]))
        self.assertEqual(iface.invalid_count, 0)

    def test_bad_checksum_counts_as_invalid(self):
        iface = make_interfacer()
        frame = bytearray(kamstrup402_frame())
        frame[-2] ^= 0xFF
        iface.ser = FakeSerial(frame)
        with mock.patch.object(mbus.time, "sleep"):
            self.assertIsNone(iface.read_data_frame([]))
        self.assertEqual(iface.invalid_count, 1)


if __name__ == "__main__":
    unittest.main()
