"""Register decoding through MinimalModbus with a simulated serial transport."""

import os
import struct
import sys
import unittest
from unittest import mock

import minimalmodbus

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
sys.path.insert(0, os.path.join(HERE, '..', 'src', 'interfacers'))

import EmonHubMinimalModbusInterfacer as modbus


class RegisterTypesTest(unittest.TestCase):
    def read_register(self, datatype, payload, expected, *, per_register=False, functioncode=None):
        transport = mock.Mock(is_open=True, port='test-modbus', baudrate=19200, timeout=1)
        function = functioncode or (4 if datatype == 'float' else 3)
        response = bytes([1, function, len(payload)]) + payload
        response += minimalmodbus._calculate_crc(response)
        transport.read.return_value = response
        instrument = minimalmodbus.Instrument(transport, 1)
        with mock.patch.object(modbus.EmonHubMinimalModbusInterfacer, 'rs485_connect'):
            interfacer = modbus.EmonHubMinimalModbusInterfacer(
                'test', datatype='float' if per_register else datatype)
        self.addCleanup(interfacer.close)
        interfacer._rs485 = instrument
        meter = {'address': 1, 'registers': [10], 'names': ['value']}
        if per_register:
            meter['datatypes'] = [datatype]
        if functioncode is not None:
            meter['functioncodes'] = [functioncode]
        interfacer.set(read_interval=1, meters={'meter': meter})
        with mock.patch.object(modbus.time, 'sleep'):
            cargo = interfacer.read()
        self.assertIsNot(cargo, False)
        self.assertEqual(cargo.realdata, [expected])
        self.assertEqual(cargo.names, ['meter_value'])
        request = transport.write.call_args.args[0]
        self.assertEqual(request[:6], bytes([1, function, 0, 10, 0, len(payload) // 2]))

    def test_unsigned_default(self):
        for value in (0, 32767, 32768, 65535):
            with self.subTest(value=value):
                self.read_register('uint', struct.pack('>H', value), value)

    def test_unsigned_per_register_input_register(self):
        self.read_register('uint', b'\xff\xff', 65535, per_register=True, functioncode=4)

    def test_signed_default_unchanged(self):
        self.read_register('int', b'\xff\xff', -1)

    def test_float_default_unchanged(self):
        self.read_register('float', struct.pack('>f', 123.5), 123.5)
