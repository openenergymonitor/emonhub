"""VE.Direct text/HEX interleaving, using the production byte parser."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from interfacers.EmonHubVEDirectInterfacer import EmonHubVEDirectInterfacer


# Asynchronous messages captured by the reporter of emonhub #160.
HEX_MESSAGES = b':ADBED001A0D5C\n:A0202000200000045\n'


def text_frame(fields):
    body = b''.join(b'\r\n' + k.encode() + b'\t' + v.encode() for k, v in fields)
    body += b'\r\nChecksum\t'
    return body + bytes([-sum(body) % 256])


def reader():
    with mock.patch.object(EmonHubVEDirectInterfacer, '_open_serial_port', return_value=None):
        return EmonHubVEDirectInterfacer('test-ve', toextract=['V', 'I'])


def feed(device, data):
    packets = []
    for byte in data:
        packet = device.input(bytes([byte]))
        if packet is not None:
            packets.append(packet)
    return packets


class TextHexTest(unittest.TestCase):
    def test_interrupted_frame_keeps_fields_and_checksum(self):
        fields = [('V', '13000'), ('I', '-120'), ('LOAD', 'ON')]
        frame = text_frame(fields)
        # Interrupt at every text byte boundary, including within labels,
        # values and CRLF, but not inside the binary checksum field.
        for offset in range(len(frame) - 1):
            with self.subTest(offset=offset):
                self.assertEqual(feed(reader(), frame[:offset] + HEX_MESSAGES + frame[offset:]), [dict(fields)])

    def test_hex_between_frames_does_not_pollute_next_checksum(self):
        first = [('V', '13000'), ('I', '-120')]
        second = [('V', '12900'), ('I', '-200')]
        self.assertEqual(feed(reader(), text_frame(first) + HEX_MESSAGES + text_frame(second)),
                         [dict(first), dict(second)])

    def test_checksum_byte_may_be_colon(self):
        # Choose a valid text field whose checksum byte is a literal ':'.
        fields = next([('V', str(v))] for v in range(100000)
                      if text_frame([('V', str(v))])[-1:] == b':')
        self.assertEqual(feed(reader(), text_frame(fields)), [dict(fields)])

    def test_invalid_text_checksum_is_still_rejected(self):
        frame = text_frame([('V', '13000')])
        invalid = frame[:-1] + bytes([(frame[-1] + 1) % 256])
        self.assertEqual(feed(reader(), HEX_MESSAGES + invalid), [{}])

    def test_plain_text_frames_are_unchanged(self):
        fields = [('V', '13000'), ('I', '-120')]
        self.assertEqual(feed(reader(), text_frame(fields)), [dict(fields)])


if __name__ == '__main__':
    unittest.main()
