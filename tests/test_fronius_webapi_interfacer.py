"""Tests for EmonHubFroniusAPIInterfacer.

Run from the repository root:  python3 -m unittest discover tests

Replies are based on the sample Solar API responses in
conf/interfacer_examples/FroniusWebAPI/readme.md (Fronius Symo).
"""

import ast
import copy
import os
import sys
import unittest
from unittest import mock

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "src", "interfacers"))

import EmonHubFroniusAPIInterfacer as fronius  # noqa: E402

OK = {"Code": 0, "Reason": "", "UserMessage": ""}

POWER_FLOW = {"Head": {"Status": OK}, "Body": {"Data": {
    "Inverters": {"1": {"DT": 122, "E_Day": 21288, "E_Total": 93495504, "E_Year": 9019699, "P": 4797}},
    "Site": {"E_Day": 21288, "E_Total": 93495504, "E_Year": 9019699, "Meter_Location": "grid",
             "Mode": "meter", "P_Akku": None, "P_Grid": -3829.89, "P_Load": -967.11, "P_PV": 4797,
             "rel_Autonomy": 100, "rel_SelfConsumption": 20.16},
    "Version": "12"}}}

INVERTER_INFO = {"Head": {"Status": OK}, "Body": {"Data": {
    "1": {"DT": 122, "ErrorCode": 0, "PVPower": 6600, "Show": 1, "StatusCode": 7, "UniqueID": "0"}}}}

PHASE_DATA = {"Head": {"Status": OK}, "Body": {"Data": {
    "IAC_L1": {"Unit": "A", "Value": 6.47}, "IAC_L2": {"Unit": "A", "Value": 6.57},
    "IAC_L3": {"Unit": "A", "Value": 6.54}, "UAC_L1": {"Unit": "V", "Value": 242.3},
    "UAC_L2": {"Unit": "V", "Value": 245}, "UAC_L3": {"Unit": "V", "Value": 245.5}}}}


def night():
    """Replies while the inverter is asleep"""
    flow = copy.deepcopy(POWER_FLOW)
    flow["Body"]["Data"]["Site"]["P_PV"] = None
    flow["Body"]["Data"]["Inverters"]["1"]["P"] = None
    info = copy.deepcopy(INVERTER_INFO)
    info["Body"]["Data"]["1"]["StatusCode"] = 3
    return {"GetPowerFlowRealtimeData": flow, "GetInverterInfo": info}


class FakeInverter:
    """Stands in for requests.get, answering from a dict of path prefix -> reply.
    A reply that is an exception is raised."""

    def __init__(self, replies):
        self.replies = replies
        self.urls = []

    def get(self, url, timeout=None):
        assert timeout is not None, "requests must have a timeout"
        self.urls.append(url)
        path = url.split("/solar_api/v1/")[1]
        for prefix, reply in self.replies.items():
            if path.startswith(prefix):
                if isinstance(reply, Exception):
                    raise reply
                response = mock.Mock()
                response.raise_for_status.return_value = None
                response.json.return_value = reply
                return response
        raise requests.exceptions.HTTPError("404 for %s" % path)


DAY = {"GetPowerFlowRealtimeData": POWER_FLOW, "GetInverterInfo": INVERTER_INFO,
       "GetInverterRealtimeData": PHASE_DATA}


class FroniusInterfacerTest(unittest.TestCase):

    def make(self, **settings):
        i = fronius.EmonHubFroniusAPIInterfacer("Fronius")
        i.set(**dict({"host": "192.168.1.11", "pubchannels": ["ToEmonCMS"]}, **settings))
        return i

    def read(self, interfacer, replies):
        fake = FakeInverter(replies)
        with mock.patch.object(fronius.requests, "get", fake.get):
            interfacer._last_time = 0
            return interfacer.read(), fake

    def test_daytime_values(self):
        c, fake = self.read(self.make(), DAY)
        self.assertEqual(c.nodeid, "fronius")
        self.assertEqual(dict(zip(c.names, c.realdata)), {
            "pv_power": 4797, "grid_power": -3829.89, "load_power": -967.11,
            "day_energy": 21288, "total_energy": 93495504, "inverter_status": 7,
            "voltage_l1": 242.3, "voltage_l2": 245, "voltage_l3": 245.5,
            "current_l1": 6.47, "current_l2": 6.57, "current_l3": 6.54})
        self.assertEqual(fake.urls[0], "http://192.168.1.11/solar_api/v1/GetPowerFlowRealtimeData.fcgi")
        self.assertIn("DeviceId=1&DataCollection=3PInverterData", fake.urls[2])

    def test_night_publishes_zero_pv_and_skips_phase_data(self):
        c, fake = self.read(self.make(), night())
        values = dict(zip(c.names, c.realdata))
        self.assertEqual(values["pv_power"], 0)
        self.assertEqual(values["inverter_status"], 3)
        self.assertNotIn("voltage_l1", values)
        self.assertNotIn("battery_power", values)
        self.assertEqual(len(fake.urls), 2)

    def test_unreachable_publishes_nothing_and_recovers(self):
        i = self.make()
        with self.assertLogs(i._log, "WARNING"):
            c, _ = self.read(i, {"GetPowerFlowRealtimeData": requests.exceptions.ConnectionError("refused")})
        self.assertIsNone(c)
        # a second failure is not logged again
        with mock.patch.object(i._log, "warning") as warning:
            self.read(i, {"GetPowerFlowRealtimeData": requests.exceptions.Timeout("timed out")})
        warning.assert_not_called()
        with self.assertLogs(i._log, "INFO"):
            c, _ = self.read(i, DAY)
        self.assertEqual(len(c.names), 12)

    def test_invalid_json_publishes_nothing(self):
        c, _ = self.read(self.make(), {"GetPowerFlowRealtimeData": {"unexpected": True}})
        self.assertIsNone(c)

    def test_api_error_code_publishes_nothing(self):
        reply = {"Head": {"Status": {"Code": 255, "Reason": "not implemented"}}, "Body": {"Data": {}}}
        c, _ = self.read(self.make(), {"GetPowerFlowRealtimeData": reply})
        self.assertIsNone(c)

    def test_optional_requests_failing_keep_power_flow_values(self):
        replies = dict(DAY, GetInverterInfo=requests.exceptions.ConnectionError("reset"))
        c, _ = self.read(self.make(), replies)
        self.assertEqual(c.names, ["pv_power", "grid_power", "load_power", "day_energy", "total_energy"])

        # single phase inverter: no 3PInverterData
        replies = dict(DAY, GetInverterRealtimeData={"Head": {"Status": {"Code": 255}}, "Body": {"Data": {}}})
        c, _ = self.read(self.make(), replies)
        self.assertEqual(c.names[-1], "inverter_status")

    def test_device_id(self):
        info = copy.deepcopy(INVERTER_INFO)
        info["Body"]["Data"]["2"] = info["Body"]["Data"].pop("1")
        c, fake = self.read(self.make(device_id="2"), dict(DAY, GetInverterInfo=info))
        self.assertEqual(dict(zip(c.names, c.realdata))["inverter_status"], 7)
        self.assertIn("DeviceId=2&", fake.urls[2])

    def test_read_interval(self):
        i = self.make(readinterval="30")
        self.assertEqual(i._settings["readinterval"], 30.0)
        c, _ = self.read(i, DAY)
        self.assertIsNotNone(c)
        with mock.patch.object(fronius.requests, "get") as get:
            self.assertIsNone(i.read())
        get.assert_not_called()

    def test_invalid_read_interval_keeps_previous(self):
        i = self.make()
        with self.assertLogs(i._log, "WARNING"):
            i.set(readinterval="often")
        self.assertEqual(i._settings["readinterval"], 10.0)

    def test_no_host_does_not_request(self):
        i = fronius.EmonHubFroniusAPIInterfacer("Fronius")
        i.set(pubchannels=["ToEmonCMS"])
        with mock.patch.object(fronius.requests, "get") as get:
            self.assertIsNone(i.read())
        get.assert_not_called()

    def test_cargo_passes_rx_processing(self):
        i = self.make()
        c, _ = self.read(i, DAY)
        rxc = i._process_rx(c)
        self.assertEqual(rxc.names[0], "pv_power")
        self.assertEqual(rxc.realdata[0], 4797)
        self.assertEqual(rxc.realdata[1], -3829.89)

    def test_listed_in_interfacers_all(self):
        # emonhub.py looks up every module in src/interfacers by name after
        # "from interfacers import *", so a module missing from __all__ stops emonhub starting
        with open(os.path.join(HERE, "..", "src", "interfacers", "__init__.py")) as f:
            tree = ast.parse(f.read())
        names = ast.literal_eval(tree.body[0].value)
        self.assertIn("EmonHubFroniusAPIInterfacer", names)


if __name__ == "__main__":
    unittest.main()
