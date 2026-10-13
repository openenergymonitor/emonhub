"""Tests for EmonModbusTcpInterfacer

Run from the repository root with: python3 -m unittest discover tests

The end to end tests run the interfacer against a minimal in-process Modbus TCP
server that simulates an enecess ecoMain, using the example configuration in
conf/interfacer_examples/modbus/ecomain.emonhub.conf. They are skipped when
pymodbus or configobj are not installed.
"""
import os
import socketserver
import struct
import sys
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "interfacers"))

import emonhub_coder as ehc
from EmonModbusTcpInterfacer import EmonModbusTcpInterfacer, decode_registers, plan_blocks

try:
    import pymodbus  # noqa: F401
    from configobj import ConfigObj
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False

ECOMAIN_CONF = os.path.join(ROOT, "conf", "interfacer_examples", "modbus", "ecomain.emonhub.conf")


def words(value, count, word_order="little"):
    """Split an integer into 16 bit registers"""
    value &= (1 << (16 * count)) - 1
    regs = [(value >> (16 * i)) & 0xFFFF for i in range(count)]
    return regs if word_order == "little" else regs[::-1]


class DecodeTest(unittest.TestCase):

    def test_big_word_order(self):
        self.assertEqual(decode_registers("I", [0x1234, 0x5678]), 0x12345678)
        self.assertEqual(decode_registers("h", [0xFF9C]), -100)
        self.assertAlmostEqual(decode_registers("f", [0x4049, 0x0FDB]), 3.14159, places=5)

    def test_little_word_order(self):
        self.assertEqual(decode_registers("i", [0x5678, 0x1234], "little"), 0x12345678)
        self.assertEqual(decode_registers("i", words(-123456, 2), "little"), -123456)
        self.assertEqual(
            decode_registers("Q", [0xDEF0, 0x9ABC, 0x5678, 0x1234], "little"),
            0x123456789ABCDEF0)
        # word order has no effect on single register values
        self.assertEqual(decode_registers("H", [0x1234], "little"), 0x1234)


class PlanBlocksTest(unittest.TestCase):

    def test_no_merge_by_default(self):
        items = [(0, 1, 1), (1, 1, 1), (2, 2, 1)]
        self.assertEqual(len(plan_blocks(items)), 3)

    def test_merges_consecutive(self):
        items = [(0, 1, 1), (1, 2, 1), (3, 4, 1), (10, 1, 1), (11, 1, 2)]
        self.assertEqual(plan_blocks(items, 125), [
            [0, 7, 1, [0, 1, 2]],
            [10, 1, 1, [3]],
            [11, 1, 2, [4]],
        ])

    def test_respects_max_block_size(self):
        items = [(0, 2, 1), (2, 2, 1), (4, 2, 1)]
        self.assertEqual(plan_blocks(items, 4), [[0, 4, 1, [0, 1]], [4, 2, 1, [2]]])

    def test_only_merges_in_configured_order(self):
        # out of order registers keep their position in the frame
        items = [(2, 1, 1), (0, 1, 1), (1, 1, 1)]
        self.assertEqual(plan_blocks(items, 125), [[2, 1, 1, [0]], [0, 2, 1, [1, 2]]])


class FakeModbusHandler(socketserver.BaseRequestHandler):
    """Minimal Modbus TCP server: function 03 only"""

    def _recv(self, n):
        data = b""
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def handle(self):
        server = self.server
        while True:
            header = self._recv(7)
            if header is None:
                return
            tid, pid, length, unit = struct.unpack(">HHHB", header)
            pdu = self._recv(length - 1)
            if pdu is None:
                return
            fc, address, count = struct.unpack(">BHH", pdu[:5])
            server.requests.append((unit, address, count))
            regs = [server.registers.get(a) for a in range(address, address + count)]
            if fc != 3 or unit != server.unit or None in regs:
                body = struct.pack(">BB", fc | 0x80, 2)
            else:
                body = struct.pack(">BB", fc, 2 * count) + struct.pack(">%dH" % count, *regs)
            self.request.sendall(struct.pack(">HHHB", tid, pid, len(body) + 1, unit) + body)


class FakeModbusServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, registers, unit):
        super().__init__(("127.0.0.1", 0), FakeModbusHandler)
        self.registers = registers
        self.unit = unit
        self.requests = []


def ecomain_registers():
    """Register image of an ecoMain, values as documented in the Modbus manual"""
    regs = {a: 0 for a in list(range(0, 352)) + list(range(1000, 1088)) + list(range(1200, 1329))}

    def put(address, value, count):
        for i, w in enumerate(words(value, count)):
            regs[address + i] = w

    put(12, 1234567890, 4)          # grid import 1234.56789 kWh
    put(28, 5000000, 4)             # grid export 5 kWh
    for p, w in enumerate((123456, -2000, 30001)):
        put(1000 + 2 * p, w, 2)     # phase power in 0.01 W
    put(1006, 151457, 2)            # total power
    for p in range(3):
        put(1200 + 3 * p, 23000 + p, 1)     # voltage 0.01 V
        put(1201 + 3 * p, 512 + p, 1)       # current 0.01 A
        put(1202 + 3 * p, -95 + p, 1)       # power factor 0.01
    for c in range(10):
        put(32 + 4 * c, (c + 1) * 1000000, 4)    # branch import kWh
        put(192 + 4 * c, (c + 1) * 100000, 4)    # branch export kWh
        put(1008 + 2 * c, (c + 1) * -1000, 2)    # branch power
        put(1209 + 3 * c, 23100, 1)
        put(1210 + 3 * c, 100 + c, 1)
        put(1211 + 3 * c, 99, 1)
    return regs


@unittest.skipUnless(HAVE_DEPS, "pymodbus and configobj are required")
class EcoMainEndToEndTest(unittest.TestCase):

    def setUp(self):
        self.server = FakeModbusServer(ecomain_registers(), unit=255)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.conf = ConfigObj(ECOMAIN_CONF, file_error=True)
        ehc.nodelist = self.conf["nodes"]
        self.interfacers = []

    def tearDown(self):
        for i in self.interfacers:
            i.close()
        self.server.shutdown()
        self.server.server_close()

    def make(self, name, **overrides):
        section = self.conf["interfacers"][name]
        init = dict(section["init_settings"])
        init["modbus_IP"] = "127.0.0.1"
        init["modbus_port"] = self.server.server_address[1]
        interfacer = EmonModbusTcpInterfacer(name, **init)
        interfacer.init_settings = init
        runtime = dict(section["runtimesettings"])
        runtime.update(overrides)
        interfacer.set(**runtime)
        self.interfacers.append(interfacer)
        return interfacer

    def read(self, interfacer):
        cargo = interfacer.read()
        self.assertIsNotNone(cargo)
        cargo = interfacer._process_rx(cargo)
        self.assertTrue(cargo)
        return dict(zip(cargo.names, cargo.realdata))

    def test_grid(self):
        values = self.read(self.make("ecoMain_grid"))
        self.assertEqual(len(values), 15)
        self.assertAlmostEqual(values["import_kwh"], 1234.56789)
        self.assertAlmostEqual(values["export_kwh"], 5)
        self.assertAlmostEqual(values["power_l1"], 1234.56)
        self.assertAlmostEqual(values["power_l2"], -20)
        self.assertAlmostEqual(values["power_l3"], 300.01)
        self.assertAlmostEqual(values["power"], 1514.57)
        self.assertAlmostEqual(values["voltage_l2"], 230.01)
        self.assertAlmostEqual(values["current_l3"], 5.14)
        self.assertAlmostEqual(values["pf_l1"], -0.95)
        # consecutive registers are read in blocks
        self.assertEqual(self.server.requests, [(255, 12, 4), (255, 28, 4), (255, 1000, 8), (255, 1200, 9)])

    def test_circuits(self):
        values = self.read(self.make("ecoMain_circuits"))
        self.assertEqual(len(values), 60)
        self.assertAlmostEqual(values["import_3"], 3)
        self.assertAlmostEqual(values["export_10"], 1)
        self.assertAlmostEqual(values["power_7"], -70)
        self.assertAlmostEqual(values["voltage_1"], 231)
        self.assertAlmostEqual(values["current_10"], 1.09)
        self.assertAlmostEqual(values["pf_5"], 0.99)
        self.assertEqual(self.server.requests, [(255, 32, 40), (255, 192, 40), (255, 1008, 20), (255, 1209, 30)])

    def test_one_request_per_value_without_block_reads(self):
        values = self.read(self.make("ecoMain_grid", max_block_size="1"))
        self.assertAlmostEqual(values["power"], 1514.57)
        self.assertEqual(len(self.server.requests), 15)

    def test_error_response_drops_frame(self):
        # unmapped register: the device returns an exception, nothing is published
        interfacer = self.make("ecoMain_grid", register=["12", "28", "1000", "1002", "1004", "1006", "1200",
                                                         "1201", "1202", "1203", "1204", "1205", "1206", "1207", "5000"])
        self.assertIsNone(interfacer.read())

    def test_interval(self):
        interfacer = self.make("ecoMain_grid")
        self.assertIsNotNone(interfacer.read())
        self.assertIsNone(interfacer.read())

    def test_reconnects(self):
        interfacer = self.make("ecoMain_grid", interval="0")
        self.read(interfacer)
        interfacer.close()
        self.read(interfacer)


if __name__ == "__main__":
    unittest.main()
