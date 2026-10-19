"""Tests for EmonHubEconet300Interfacer.

Run from the repository root:  python3 -m unittest discover tests

Fixtures in tests/fixtures/econet300 are real /econet/regParams and /econet/editParams replies
from a Grant Aerona R290 (ecoMAX360i, firmware S024.24) with three circuits: circuit 1 fixed
flow temperature, circuit 2 mixed and weather compensated, circuit 3 fixed. DHW is disabled.
Identifiers are anonymised.
"""

import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "src", "interfacers"))

import EmonHubEconet300Interfacer as econet  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "econet300")


def fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


class ToNumberTest(unittest.TestCase):

    def test_values(self):
        self.assertEqual(econet.to_number(38.8), 38.8)
        self.assertEqual(econet.to_number("18.33"), 18.33)
        self.assertEqual(econet.to_number("0"), 0)
        self.assertEqual(econet.to_number("on"), 1)
        self.assertEqual(econet.to_number("off"), 0)
        self.assertEqual(econet.to_number(True), 1)
        self.assertIsNone(econet.to_number("---"))
        self.assertIsNone(econet.to_number("S024.24"))
        self.assertIsNone(econet.to_number(None))


class ExtractValuesTest(unittest.TestCase):

    def setUp(self):
        self.data, self.missing = econet.extract_values(
            fixture("regParams.json"), fixture("editParams.json"), econet.PARAMS_GRANT_AERONA_R290)

    def test_all_numeric(self):
        for name, value in self.data.items():
            self.assertIsInstance(value, float, name)

    def test_values(self):
        self.assertEqual(self.data["flow_temp"], 38.8)
        self.assertEqual(self.data["return_temp"], 33.2)
        self.assertEqual(self.data["input_power"], 4.09)
        self.assertEqual(self.data["output_power"], 18.33)  # string in the JSON
        self.assertEqual(self.data["system_pressure"], 1.5)  # string in the JSON
        self.assertEqual(self.data["no_heat_demanded"], 0)
        self.assertEqual(self.data["circuit1_pump"], 1)  # 'on' in the JSON
        self.assertEqual(self.data["backup_heater"], 0)  # 'off' in the JSON
        self.assertEqual(self.data["circuit2_weather_curve"], 1.1)
        self.assertEqual(self.data["circuit2_mixer_valve"], 44.2)
        self.assertEqual(self.data["circuit3_room_temp"], 19.03)
        self.assertEqual(self.data["circuit3_max_flow_temp"], 45)

    def test_missing(self):
        self.assertEqual(set(self.missing), {
            "dhw_temp",                      # '---', DHW disabled
            "circuit1_weather_curve",        # circuit 1 not weather compensated
            "circuit1_weather_curve_shift",
            "circuit2_room_temp",            # 999.0, no circuit 2 thermostat
        })
        self.assertEqual(self.missing["circuit2_room_temp"], "sensor not fitted")


class WarnOnceTest(unittest.TestCase):

    def setUp(self):
        self.reg = fixture("regParams.json")
        self.edit = fixture("editParams.json")
        self.iface = econet.EmonHubEconet300Interfacer("econet", "host", "admin", "admin", 60)
        self.iface._log = mock.Mock()
        self.iface._econet_http_request = lambda path: self.reg if path == "/econet/regParams" else self.edit

    def warned(self):
        return [c.args[0].split(":")[0] for c in self.iface._log.warning.call_args_list]

    def test_warns_once(self):
        cargo = self.iface._fetch_data()
        self.assertIn("flow_temp", cargo.names)
        self.assertEqual(len(cargo.names), len(cargo.realdata))
        self.assertEqual(len(self.warned()), 4)

        self.iface._fetch_data()
        self.assertEqual(len(self.warned()), 4)
        self.iface._log.debug.assert_called_with("Skipped 4 missing values")
        self.assertEqual(self.iface._log.debug.call_count, 2)

    def test_reappears(self):
        self.iface._fetch_data()
        self.edit["data"]["273"] = {"value": 0.8}
        cargo = self.iface._fetch_data()
        self.assertIn("circuit1_weather_curve", cargo.names)
        self.iface._log.info.assert_called_once_with("circuit1_weather_curve is now available")

        del self.edit["data"]["273"]
        self.iface._fetch_data()
        self.assertEqual(self.warned().count("Unable to retrieve circuit1_weather_curve"), 2)


if __name__ == "__main__":
    unittest.main()
