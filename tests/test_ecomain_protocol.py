import unittest

from ecomain.protocol import (
    EcoMainReadError,
    EcoMainReader,
    branch_addresses,
    decode_i16,
    decode_i32,
    decode_text,
    decode_u16,
    decode_u64,
)


def words_little(value, word_count):
    return [(value >> (16 * index)) & 0xFFFF for index in range(word_count)]


class FakeResponse:
    def __init__(self, registers, error=False):
        self.registers = registers
        self._error = error

    def isError(self):
        return self._error


class FakeClient:
    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls = []

    def read_holding_registers(self, address, count, slave):
        self.calls.append((address, count, slave))
        return self.responses[(address, count)]


class AddressTests(unittest.TestCase):
    def test_branch_addresses_are_zero_based(self):
        self.assertEqual(
            branch_addresses(0, 1),
            {
                "energy": 32,
                "return_energy": 192,
                "power": 1008,
                "voltage": 1209,
                "current": 1210,
                "power_factor": 1211,
            },
        )
        self.assertEqual(branch_addresses(3, 10)["energy"], 188)
        self.assertEqual(branch_addresses(3, 10)["power_factor"], 1328)

    def test_branch_address_range_is_validated(self):
        for device, channel in [(-1, 1), (4, 1), (0, 0), (0, 11)]:
            with self.subTest(device=device, channel=channel):
                with self.assertRaises(ValueError):
                    branch_addresses(device, channel)


class DecoderTests(unittest.TestCase):
    def test_numeric_decoders_use_big_bytes_little_words(self):
        self.assertEqual(decode_u16([0x1234]), 0x1234)
        self.assertEqual(decode_i16([0xFF9C]), -100)
        self.assertEqual(decode_i32([0x5678, 0x1234]), 0x12345678)
        self.assertEqual(
            decode_u64([0xDEF0, 0x9ABC, 0x5678, 0x1234]),
            0x123456789ABCDEF0,
        )

    def test_text_uses_low_byte_then_high_byte_per_register(self):
        self.assertEqual(decode_text([0x4241, 0x0043]), "ABC")


class ReaderTests(unittest.TestCase):
    def assert_sample_almost_equal(self, sample, expected):
        self.assertEqual(set(sample), set(expected))
        for name, value in expected.items():
            self.assertAlmostEqual(sample[name], value)

    def test_read_uses_unit_keyword_for_legacy_client(self):
        class LegacyClient:
            def __init__(self):
                self.kwargs = None

            def read_holding_registers(self, address, count=1, **kwargs):
                self.kwargs = kwargs
                return FakeResponse([123])

        client = LegacyClient()

        registers = EcoMainReader(client)._read(10, 1)

        self.assertEqual(registers, [123])
        self.assertEqual(client.kwargs, {"unit": 255})

    def test_read_uses_device_id_keyword_for_modern_client(self):
        class ModernClient:
            def __init__(self):
                self.device_id = None

            def read_holding_registers(
                self, address, *, count=1, device_id=1, no_response_expected=False
            ):
                self.device_id = device_id
                return FakeResponse([456])

        client = ModernClient()

        registers = EcoMainReader(client)._read(10, 1)

        self.assertEqual(registers, [456])
        self.assertEqual(client.device_id, 255)

    def test_read_grid_decodes_three_exact_read_only_blocks(self):
        energy = []
        for value in (1_000_000, 2_000_000, 3_000_000, 6_000_000):
            energy.extend(words_little(value, 4))
        for value in (100_000, 200_000, 300_000, 600_000):
            energy.extend(words_little(value, 4))

        power = []
        for value in (12_345, -2_500, 3_000, 12_845):
            power.extend(words_little(value, 2))

        electric = [23001, 123, 98, 23002, 456, 0xFF9C, 22999, 789, 100]
        client = FakeClient(
            {
                (0, 32): FakeResponse(energy),
                (1000, 8): FakeResponse(power),
                (1200, 9): FakeResponse(electric),
            }
        )

        sample = EcoMainReader(client).read_grid()

        self.assertEqual(set(sample), {"power", "energy", "return_energy", "phases"})
        self.assert_sample_almost_equal(
            {name: sample[name] for name in ("power", "energy", "return_energy")},
            {"power": 128.45, "energy": 6.0, "return_energy": 0.6},
        )
        expected_phases = (
            {
                "power": 123.45,
                "voltage": 230.01,
                "current": 1.23,
                "power_factor": 0.98,
            },
            {
                "power": -25.0,
                "voltage": 230.02,
                "current": 4.56,
                "power_factor": -1.0,
            },
            {
                "power": 30.0,
                "voltage": 229.99,
                "current": 7.89,
                "power_factor": 1.0,
            },
        )
        self.assertEqual(len(sample["phases"]), 3)
        for phase, expected in zip(sample["phases"], expected_phases):
            self.assert_sample_almost_equal(phase, expected)
        self.assertEqual(
            client.calls,
            [(0, 32, 255), (1000, 8, 255), (1200, 9, 255)],
        )

    def test_read_branch_device_decodes_ten_channels_from_four_blocks(self):
        forward = []
        reverse = []
        power = []
        electric = []
        for channel in range(1, 11):
            forward.extend(words_little(channel * 1_000_000, 4))
            reverse.extend(words_little(channel * 100_000, 4))
            power.extend(words_little(-channel * 100, 2))
            electric.extend((22000 + channel, channel * 10, 100 - channel))
        client = FakeClient(
            {
                (112, 40): FakeResponse(forward),
                (272, 40): FakeResponse(reverse),
                (1048, 20): FakeResponse(power),
                (1269, 30): FakeResponse(electric),
            }
        )

        samples = EcoMainReader(client).read_branch_device(2)

        self.assertEqual(list(samples), list(range(1, 11)))
        self.assert_sample_almost_equal(
            samples[1],
            {
                "power": -1.0,
                "energy": 1.0,
                "return_energy": 0.1,
                "voltage": 220.01,
                "current": 0.1,
                "power_factor": 0.99,
            },
        )
        self.assert_sample_almost_equal(
            samples[10],
            {
                "power": -10.0,
                "energy": 10.0,
                "return_energy": 1.0,
                "voltage": 220.1,
                "current": 1.0,
                "power_factor": 0.9,
            },
        )
        self.assertEqual(
            client.calls,
            [
                (112, 40, 255),
                (272, 40, 255),
                (1048, 20, 255),
                (1269, 30, 255),
            ],
        )

    def test_read_device_info_decodes_text_and_six_version_registers(self):
        registers = [
            0x4345,
            0x3130,
            0x4E53,
            0x3231,
            0x3433,
            0x3635,
            0x3837,
            0x3039,
            101,
            102,
            103,
            104,
            105,
            106,
        ]
        client = FakeClient({(3000, 14): FakeResponse(registers)})

        info = EcoMainReader(client).read_device_info()

        self.assertEqual(
            info,
            {
                "model": "EC01",
                "serial": "SN1234567890",
                "versions": {
                    "hardware": 101,
                    "ecomain_software": 102,
                    "ecomain_firmware": 103,
                    "ecosub_1_firmware": 104,
                    "ecosub_2_firmware": 105,
                    "ecosub_3_firmware": 106,
                },
            },
        )
        self.assertEqual(client.calls, [(3000, 14, 255)])

    def test_read_rejects_error_missing_and_wrong_length_responses(self):
        class MissingRegistersResponse:
            def isError(self):
                return False

        for response in (
            FakeResponse([0] * 32, error=True),
            MissingRegistersResponse(),
            FakeResponse([0] * 31),
            FakeResponse([0] * 33),
        ):
            with self.subTest(response=response):
                client = FakeClient({(0, 32): response})
                with self.assertRaises(EcoMainReadError):
                    EcoMainReader(client).read_grid()

    def test_reader_wraps_client_read_errors(self):
        client = FakeClient({})

        with self.assertRaises(EcoMainReadError) as raised:
            EcoMainReader(client).read_grid()

        self.assertIsInstance(raised.exception.__cause__, KeyError)

    def test_reader_never_reads_online_status_registers(self):
        energy = FakeResponse([0] * 32)
        power = FakeResponse([0] * 8)
        electric = FakeResponse([0] * 9)
        info = FakeResponse([0] * 14)
        client = FakeClient(
            {
                (0, 32): energy,
                (1000, 8): power,
                (1200, 9): electric,
                (3000, 14): info,
            }
        )
        reader = EcoMainReader(client)

        reader.read_grid()
        reader.read_device_info()

        self.assertTrue(
            all(address not in (3101, 3102, 3103) for address, _, _ in client.calls)
        )
