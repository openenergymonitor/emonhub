"""Exercise the serial reader using a real local pseudo-terminal (no hardware)."""
import os
import select
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from interfacers.EmonHubSerialInterfacer import EmonHubSerialInterfacer


@unittest.skipUnless(os.name == 'posix', 'requires a POSIX pseudo-terminal')
class SerialReaderTest(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = os.openpty()
        self.reader = EmonHubSerialInterfacer('test-serial', os.ttyname(self.slave))
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        self.addCleanup(self.reader.close)

    def receive(self, data):
        os.write(self.master, data)
        ready, _, _ = select.select([self.reader._ser], [], [], 1)
        self.assertTrue(ready, 'test bytes did not reach the serial port')
        return self.reader.read()

    def test_invalid_utf8_line_does_not_prevent_next_reading(self):
        self.assertFalse(self.receive(b'10 123\xff\r\n'))
        cargo = self.receive(b'10 456\r\n')
        self.assertEqual(cargo.nodeid, 10)
        self.assertEqual(cargo.realdata, ['456'])

    def test_invalid_partial_line_is_discarded_as_a_whole(self):
        self.assertFalse(self.receive(b'10 12\xff'))
        self.assertFalse(self.receive(b'34\r\n'))
        cargo = self.receive(b'11 567\r\n')
        self.assertEqual(cargo.nodeid, 11)
        self.assertEqual(cargo.realdata, ['567'])

    def test_valid_partial_line_is_reassembled(self):
        self.assertFalse(self.receive(b'10 12'))
        cargo = self.receive(b'34\r\n')
        self.assertEqual(cargo.nodeid, 10)
        self.assertEqual(cargo.realdata, ['1234'])

    def test_nodeoffset_preserves_all_values(self):
        self.reader.set(nodeoffset=42)
        cargo = self.receive(b'10 123\r\n')
        self.assertEqual(cargo.nodeid, 42)
        self.assertEqual(cargo.realdata, ['10', '123'])


if __name__ == '__main__':
    unittest.main()
