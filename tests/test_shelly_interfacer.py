"""Tests for EmonHubShellyInterfacer.

Run from the repository root:  python3 -m unittest discover tests

Fixtures in tests/fixtures/shelly are real Shelly.GetStatus / Shelly.GetDeviceInfo
replies and websocket notifications from Gen2 Pro devices (firmware 2.0.1), with
identifiers anonymised.
"""

import copy
import hashlib
import json
import os
import sys
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "src", "interfacers"))

import EmonHubShellyInterfacer as shelly  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "shelly")


def fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


def as_dict(values):
    """name -> value from (name, value) or (name, kind, value) tuples."""
    return {v[0]: v[-1] for v in values}


class StatusToValuesTest(unittest.TestCase):

    def test_pro2pm_default_fields(self):
        values = shelly.select_values(shelly.status_to_values(fixture("pro2pm_status.json")))
        self.assertEqual([n for n, _ in values], [
            "switch0_output", "switch0_power", "switch0_voltage", "switch0_current", "switch0_pf", "switch0_energy",
            "switch1_output", "switch1_power", "switch1_voltage", "switch1_current", "switch1_pf", "switch1_energy",
        ])
        v = as_dict(values)
        self.assertEqual(v["switch0_output"], 1)
        self.assertEqual(v["switch0_power"], 2663.7)
        self.assertEqual(v["switch1_energy"], 12853756.545)

    def test_pro1pm_default_fields(self):
        v = as_dict(shelly.select_values(shelly.status_to_values(fixture("pro1pm_status.json"))))
        self.assertEqual(set(v), {"switch0_output", "switch0_power", "switch0_voltage",
                                  "switch0_current", "switch0_pf", "switch0_energy"})

    def test_dimmer_default_fields(self):
        v = as_dict(shelly.select_values(shelly.status_to_values(fixture("prodimmer0110vpm_status.json"))))
        self.assertEqual(v, {
            "light0_output": 1,
            "light0_brightness": 100,
            "light0_power": 0.0,
            "light0_voltage": 224.3,
            "light0_current": 0.0,
            "light0_energy": 8851067.839,
        })

    def test_pro3em_triphase_default_fields(self):
        v = as_dict(shelly.select_values(shelly.status_to_values(fixture("pro3em_status.json"))))
        for phase in "abc":
            for kind in ("power", "voltage", "current", "pf", "energy"):
                self.assertIn(phase + "_" + kind, v)
        self.assertEqual(v["a_power"], 33.2)
        self.assertEqual(v["a_energy"], 20081.72)
        self.assertEqual(v["total_power"], 33.241)
        self.assertEqual(v["total_energy"], 20083.49)
        # Not a default field, and null on this device: absent either way
        self.assertNotIn("n_current", v)
        # temperature:0 is the device's own sensor, not a metered channel
        self.assertNotIn("temperature", v)

    def test_fields_select_and_order(self):
        values = shelly.select_values(shelly.status_to_values(fixture("pro3em_status.json")),
                                      ["a_energy", "a_power", "a_freq", "no_such_input"])
        self.assertEqual(values, [("a_energy", 20081.72), ("a_power", 33.2), ("a_freq", 50.0)])

    def test_optional_fields_available(self):
        v = as_dict(shelly.status_to_values(fixture("pro2pm_status.json")))
        self.assertEqual(v["switch0_freq"], 50.0)
        self.assertEqual(v["switch0_ret_energy"], 0.0)
        self.assertEqual(v["switch1_ret_energy"], 5827.0)
        self.assertEqual(v["switch0_temperature"], 61.7)
        v = as_dict(shelly.status_to_values(fixture("pro3em_status.json")))
        self.assertEqual(v["b_ret_energy"], 5.12)
        self.assertEqual(v["a_apparent_power"], 123.7)

    def test_zero_energy_counter_is_skipped(self):
        status = fixture("pro2pm_status.json")
        status["switch:0"]["aenergy"]["total"] = 0
        v = as_dict(shelly.status_to_values(status))
        self.assertNotIn("switch0_energy", v)
        self.assertNotIn("switch0_ret_energy", v)
        self.assertIn("switch1_energy", v)

        status = fixture("pro3em_status.json")
        status["emdata:0"]["a_total_act_energy"] = 0.0
        v = as_dict(shelly.status_to_values(status))
        self.assertNotIn("a_energy", v)
        self.assertNotIn("a_ret_energy", v)
        self.assertIn("b_energy", v)

    def test_em1_and_pm1_naming(self):
        status = {
            "em1:0": {"id": 0, "act_power": 12.5, "voltage": 230.1, "current": 0.1, "pf": 0.5},
            "em1data:0": {"id": 0, "total_act_energy": 1000.5, "total_act_ret_energy": 2.0},
            "pm1:0": {"id": 0, "apower": 3.0, "aenergy": {"total": 7.0}},
        }
        v = as_dict(shelly.select_values(shelly.status_to_values(status)))
        self.assertEqual(v, {
            "em1_0_power": 12.5, "em1_0_voltage": 230.1, "em1_0_current": 0.1, "em1_0_pf": 0.5,
            "em1_0_energy": 1000.5,
            "pm1_0_power": 3.0, "pm1_0_energy": 7.0,
        })

    def test_cover_position(self):
        status = {"cover:0": {"id": 0, "apower": 0.0, "current_pos": 42, "aenergy": {"total": 5.0}}}
        v = as_dict(shelly.status_to_values(status))
        self.assertEqual(v["cover0_position"], 42)


class MergeStatusTest(unittest.TestCase):

    def test_notifications_merge_into_status(self):
        status = fixture("pro2pm_status.json")
        for frame in fixture("pro2pm_notifications.json"):
            shelly.merge_status(status, frame["params"])
        s0 = status["switch:0"]
        self.assertIs(s0["output"], False)
        self.assertEqual(s0["apower"], 0.0)
        self.assertEqual(s0["aenergy"]["total"], 12953094.683)
        self.assertEqual(s0["aenergy"]["minute_ts"], 1791756540)
        # untouched keys survive a partial update
        self.assertEqual(s0["temperature"]["tC"], 61.7)
        self.assertEqual(s0["ret_aenergy"]["total"], 0.0)
        # "ts" is notification metadata, not a component
        self.assertNotIn("ts", status)

    def test_merge_into_null(self):
        status = {"switch:0": {"aenergy": None}}
        shelly.merge_status(status, {"switch:0": {"aenergy": {"total": 1.0}}})
        self.assertEqual(status["switch:0"]["aenergy"], {"total": 1.0})

    def test_merge_dict_over_scalar(self):
        status = {"switch:0": {"temperature": 40}}
        shelly.merge_status(status, {"switch:0": {"temperature": {"tC": 41.0}}})
        self.assertEqual(status["switch:0"]["temperature"], {"tC": 41.0})


class DigestAuthTest(unittest.TestCase):

    def test_response_and_nc(self):
        challenge = {"auth_type": "digest", "nonce": 1625038762, "nc": 1,
                     "realm": "shellypro2pm-aabbcc000002", "algorithm": "SHA-256"}
        auth = shelly.DigestAuth("secret")
        auth.update_challenge(challenge)

        def h(s):
            return hashlib.sha256(s.encode()).hexdigest()

        ha1 = h("admin:shellypro2pm-aabbcc000002:secret")
        ha2 = h("dummy_method:dummy_uri")

        first = auth.get_auth()
        self.assertEqual(first["username"], "admin")
        self.assertEqual(first["nc"], 1)
        self.assertEqual(first["response"],
                         h("%s:1625038762:1:%s:auth:%s" % (ha1, first["cnonce"], ha2)))
        second = auth.get_auth()
        self.assertEqual(second["nc"], 2)
        self.assertNotEqual(first["cnonce"], second["cnonce"])

    def test_unsupported_algorithm(self):
        auth = shelly.DigestAuth("secret")
        with self.assertRaises(ValueError):
            auth.update_challenge({"nonce": 1, "realm": "r", "algorithm": "MD5"})


class FakeWsDevice(shelly.ShellyWsDevice):
    """A websocket device with the socket replaced by a list of sent frames."""

    def __init__(self, password=None):
        super().__init__("dev", "shelly.local", password=password, log=mock.Mock())
        self.sent = []

    def _send(self, frame):
        self.sent.append(frame)

    def receive(self, frame):
        self._on_frame(frame)


class WsDeviceTest(unittest.TestCase):

    def test_open_requests_info_and_status(self):
        d = FakeWsDevice()
        d._on_connected()
        self.assertEqual([f["method"] for f in d.sent], ["Shelly.GetDeviceInfo", "Shelly.GetStatus"])
        self.assertTrue(all(f["src"] == d.src for f in d.sent))
        self.assertEqual(len({f["id"] for f in d.sent}), 2)

    def test_status_reply_then_notifications(self):
        d = FakeWsDevice()
        d._on_connected()
        self.assertIsNone(d.snapshot()[0])
        status_req = d.sent[1]
        d.receive({"id": status_req["id"], "src": "shellypro2pm-aabbcc000002", "dst": d.src,
                   "result": fixture("pro2pm_status.json")})
        self.assertEqual(d.snapshot()[0]["switch:0"]["output"], True)
        for frame in fixture("pro2pm_notifications.json"):
            d.receive(frame)
        self.assertEqual(d.snapshot()[0]["switch:0"]["output"], False)

    def test_notification_before_status_is_ignored(self):
        d = FakeWsDevice()
        d._on_connected()
        d.receive(fixture("pro2pm_notifications.json")[0])
        self.assertIsNone(d.snapshot()[0])

    def test_full_status_notification_replaces(self):
        d = FakeWsDevice()
        d._on_connected()
        d.receive({"src": "x", "dst": d.src, "method": "NotifyFullStatus",
                   "params": dict(fixture("pro1pm_status.json"), ts=1.0)})
        self.assertIn("switch:0", d.snapshot()[0])

    def test_quiet_device_stays_current_until_disconnected(self):
        d = FakeWsDevice()
        d._on_connected()
        d.receive({"id": d.sent[1]["id"], "result": fixture("pro1pm_status.json")})
        with mock.patch.object(shelly.time, "time", return_value=time.time() + 3600):
            self.assertIsNotNone(d.snapshot()[0])
        d._on_disconnected()
        self.assertIsNone(d.snapshot()[0])

    def test_poll_resyncs_only_every_resync_interval(self):
        d = FakeWsDevice()
        d.poll()
        self.assertEqual(d.sent, [])
        d._on_connected()
        d.receive({"id": d.sent[1]["id"], "result": fixture("pro1pm_status.json")})
        d.sent.clear()
        d.poll()
        self.assertEqual(d.sent, [])
        later = time.time() + shelly.ShellyWsDevice.RESYNC_INTERVAL
        with mock.patch.object(shelly.time, "time", return_value=later):
            d.poll()
            d.poll()
        self.assertEqual([f["method"] for f in d.sent], ["Shelly.GetStatus"])

    def test_auth_challenge_resends_with_auth(self):
        d = FakeWsDevice(password="secret")
        d._on_connected()
        req = d.sent[1]
        challenge = {"auth_type": "digest", "nonce": 99, "nc": 1, "realm": "r", "algorithm": "SHA-256"}
        d.receive({"id": req["id"], "error": {"code": 401, "message": json.dumps(challenge)}})
        retry = d.sent[-1]
        self.assertEqual(retry["method"], "Shelly.GetStatus")
        self.assertNotEqual(retry["id"], req["id"])
        self.assertEqual(retry["auth"]["nonce"], 99)
        # later requests carry auth without a further challenge
        d._request("Shelly.GetStatus")
        self.assertIn("auth", d.sent[-1])
        self.assertEqual(d.sent[-1]["auth"]["nc"], retry["auth"]["nc"] + 1)

    def test_auth_rejected_does_not_loop(self):
        d = FakeWsDevice(password="wrong")
        d._on_connected()
        challenge = {"nonce": 99, "realm": "r", "algorithm": "SHA-256"}
        d.receive({"id": d.sent[1]["id"], "error": {"code": 401, "message": json.dumps(challenge)}})
        n = len(d.sent)
        d.receive({"id": d.sent[-1]["id"], "error": {"code": 401, "message": json.dumps(challenge)}})
        self.assertEqual(len(d.sent), n)
        d._log.error.assert_called()

    def test_auth_required_without_password(self):
        d = FakeWsDevice()
        d._on_connected()
        challenge = {"nonce": 99, "realm": "r", "algorithm": "SHA-256"}
        n = len(d.sent)
        d.receive({"id": d.sent[1]["id"], "error": {"code": 401, "message": json.dumps(challenge)}})
        self.assertEqual(len(d.sent), n)
        d._log.error.assert_called()

    def test_connection_error_clears_status_at_once(self):
        d = FakeWsDevice()
        d._on_connected()
        d.receive({"id": d.sent[1]["id"], "result": fixture("pro1pm_status.json")})
        d._on_ws_error(ValueError("error in a callback"))
        self.assertIsNotNone(d.snapshot()[0])
        d._on_ws_error(shelly.websocket.WebSocketTimeoutException("ping/pong timed out"))
        self.assertIsNone(d.snapshot()[0])

    def test_snapshot_time_is_now_while_connected(self):
        d = FakeWsDevice()
        d._on_connected()
        d.receive({"id": d.sent[1]["id"], "result": fixture("pro1pm_status.json")})
        with mock.patch.object(shelly.time, "time", return_value=5000.0):
            self.assertEqual(d.snapshot()[1], 5000.0)

    def test_device_info_logged(self):
        d = FakeWsDevice()
        d._on_connected()
        d.receive({"id": d.sent[0]["id"], "result": fixture("pro3em_deviceinfo.json")})
        msg = d._log.info.call_args[0][0] % d._log.info.call_args[0][1:]
        self.assertIn("shellypro3em-aabbcc000003", msg)
        self.assertIn("2.0.1", msg)


class HttpDeviceTest(unittest.TestCase):

    def make(self, password=None):
        return shelly.ShellyHttpDevice("dev", "shelly.local", password=password, log=mock.Mock())

    def test_fetch_replaces_status(self):
        d = self.make()
        reply = mock.Mock(status_code=200)
        reply.json.return_value = fixture("pro1pm_status.json")
        with mock.patch.object(shelly.requests, "get", return_value=reply) as get:
            d._fetch()
        url = get.call_args[0][0]
        self.assertEqual(url, "http://shelly.local/rpc/Shelly.GetStatus")
        self.assertIsNone(get.call_args[1]["auth"])
        self.assertIn("switch:0", d.snapshot()[0])

    def test_fetch_uses_digest_auth(self):
        d = self.make(password="secret")
        reply = mock.Mock(status_code=200)
        reply.json.return_value = {}
        with mock.patch.object(shelly.requests, "get", return_value=reply) as get:
            d._fetch()
        auth = get.call_args[1]["auth"]
        self.assertIsInstance(auth, shelly.requests.auth.HTTPDigestAuth)
        self.assertEqual(auth.username, "admin")

    def test_failed_poll_clears_status(self):
        d = self.make()
        reply = mock.Mock(status_code=200)
        reply.json.return_value = fixture("pro1pm_status.json")
        with mock.patch.object(shelly.requests, "get", return_value=reply):
            d._fetch()
        self.assertIsNotNone(d.snapshot()[0])
        with mock.patch.object(shelly.requests, "get", side_effect=shelly.requests.ConnectionError("down")):
            d._fetch()
        self.assertIsNone(d.snapshot()[0])
        d._log.warning.assert_called()

    def test_snapshot_time_is_fetch_time(self):
        d = self.make()
        reply = mock.Mock(status_code=200)
        reply.json.return_value = fixture("pro1pm_status.json")
        with mock.patch.object(shelly.requests, "get", return_value=reply), \
                mock.patch.object(shelly.time, "time", return_value=990.0):
            d._fetch()
        with mock.patch.object(shelly.time, "time", return_value=1000.0):
            self.assertEqual(d.snapshot()[1], 990.0)

    def test_repeated_failures_warn_once(self):
        d = self.make()
        with mock.patch.object(shelly.requests, "get", side_effect=shelly.requests.ConnectionError("down")):
            d._fetch()
            d._fetch()
            d._fetch()
        self.assertEqual(d._log.warning.call_count, 1)
        reply = mock.Mock(status_code=200)
        reply.json.return_value = {}
        with mock.patch.object(shelly.requests, "get", return_value=reply):
            d._fetch()
        d._log.info.assert_called()


class FakeDevice:
    def __init__(self, status):
        self.status = status
        self.polls = 0
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def snapshot(self):
        if self.status is None:
            return None, None
        return copy.deepcopy(self.status), shelly.time.time()

    def poll(self):
        self.polls += 1

    def stop(self):
        self.stopped = True


class InterfacerTest(unittest.TestCase):

    def make(self):
        with mock.patch.object(shelly, "make_device") as make_device:
            make_device.side_effect = lambda name, cfg, log: FakeDevice(None)
            i = shelly.EmonHubShellyInterfacer("Shelly")
            i.set(read_interval="10", pubchannels=["ToEmonCMS"], devices={
                "heatpump": {"host": "shellypro3em-aabbcc000003.local", "fields": ["a_power", "a_energy"]},
                "buffer_imm_1_2": {"host": "shellypro2pm-aabbcc000002.local"},
                "offline": {"host": "10.0.0.9"},
            })
        return i

    def test_set_creates_devices(self):
        with mock.patch.object(shelly, "make_device") as make_device:
            make_device.side_effect = lambda name, cfg, log: FakeDevice(None)
            i = shelly.EmonHubShellyInterfacer("Shelly")
            i.set(read_interval="10", devices={
                "hp": {"host": "a.local", "fields": "a_power", "password": "pw", "transport": "http"},
            })
        cfg = make_device.call_args[0][1]
        self.assertEqual(cfg, {"host": "a.local", "fields": ["a_power"], "password": "pw", "transport": "http"})
        self.assertEqual(i._settings["read_interval"], 10.0)

    def test_set_unchanged_devices_keeps_threads(self):
        i = self.make()
        before = dict(i._devices)
        with mock.patch.object(shelly, "make_device") as make_device:
            i.set(read_interval="10", devices={
                "heatpump": {"host": "shellypro3em-aabbcc000003.local", "fields": ["a_power", "a_energy"]},
                "buffer_imm_1_2": {"host": "shellypro2pm-aabbcc000002.local"},
                "offline": {"host": "10.0.0.9"},
            })
        make_device.assert_not_called()
        self.assertEqual(i._devices, before)

    def test_set_changed_device_restarts_only_it(self):
        i = self.make()
        old = dict(i._devices)
        with mock.patch.object(shelly, "make_device") as make_device:
            make_device.side_effect = lambda name, cfg, log: FakeDevice(None)
            i.set(read_interval="10", devices={
                "heatpump": {"host": "shellypro3em-aabbcc000003.local", "fields": ["a_power"]},
                "buffer_imm_1_2": {"host": "shellypro2pm-aabbcc000002.local"},
            })
        self.assertTrue(old["heatpump"].stopped)
        self.assertTrue(old["offline"].stopped)
        self.assertFalse(old["buffer_imm_1_2"].stopped)
        self.assertIs(i._devices["buffer_imm_1_2"], old["buffer_imm_1_2"])
        self.assertEqual(sorted(i._devices), ["buffer_imm_1_2", "heatpump"])

    def test_read_emits_one_cargo_per_live_device(self):
        i = self.make()
        i._devices["heatpump"].status = fixture("pro3em_status.json")
        i._devices["buffer_imm_1_2"].status = fixture("pro2pm_status.json")

        with mock.patch.object(shelly.time, "time", return_value=1000.0):
            first = i.read()
            second = i.read()
            third = i.read()

        cargos = [c for c in (first, second, third) if c]
        self.assertEqual([c.nodeid for c in cargos], ["heatpump", "buffer_imm_1_2"])
        hp = cargos[0]
        self.assertEqual(hp.names, ["a_power", "a_energy"])
        self.assertEqual(hp.realdata, [33.2, 20081.72])
        self.assertEqual(hp.timestamp, 1000.0)
        self.assertEqual(len(cargos[1].names), 12)
        self.assertTrue(all(d.polls == 1 for d in i._devices.values()))

    def test_read_waits_for_next_interval(self):
        i = self.make()
        i._devices["heatpump"].status = fixture("pro3em_status.json")
        with mock.patch.object(shelly.time, "time", return_value=1000.0):
            self.assertTrue(i.read())
        with mock.patch.object(shelly.time, "time", return_value=1009.9):
            self.assertFalse(i.read())
        with mock.patch.object(shelly.time, "time", return_value=1010.0):
            self.assertTrue(i.read())

    def test_device_with_no_wanted_values_emits_nothing(self):
        i = self.make()
        i._devices["heatpump"].status = {"sys": {}}
        with mock.patch.object(shelly.time, "time", return_value=1000.0):
            self.assertFalse(i.read())

    def test_read_interval_minimum(self):
        i = self.make()
        i.set(read_interval="0")
        self.assertEqual(i._settings["read_interval"], 1.0)

    def test_unknown_transport_is_skipped(self):
        with mock.patch.object(shelly, "make_device") as make_device:
            i = shelly.EmonHubShellyInterfacer("Shelly")
            i.set(devices={"hp": {"host": "a.local", "transport": "mqtt"}})
        make_device.assert_not_called()
        self.assertEqual(i._devices, {})

    def test_missing_field_warns_once(self):
        i = self.make()
        i._devices["heatpump"].status = {"em:0": {"a_act_power": 33.2}}
        i._log = mock.Mock()
        with mock.patch.object(shelly.time, "time", return_value=1000.0):
            i.read()
        with mock.patch.object(shelly.time, "time", return_value=1010.0):
            i.read()
        self.assertEqual(i._log.warning.call_count, 1)
        self.assertIn("a_energy", i._log.warning.call_args[0])

    def test_set_after_stop_starts_nothing(self):
        i = self.make()
        i._stop_devices()
        with mock.patch.object(shelly, "make_device") as make_device:
            i.set(devices={"hp": {"host": "a.local"}})
        make_device.assert_not_called()
        self.assertEqual(i._devices, {})

    def test_stop_devices(self):
        i = self.make()
        devices = list(i._devices.values())
        i._stop_devices()
        self.assertTrue(all(d.stopped for d in devices))
        self.assertEqual(i._devices, {})


class MakeDeviceTest(unittest.TestCase):

    def test_ws_when_available(self):
        with mock.patch.object(shelly, "websocket", mock.Mock()):
            d = shelly.make_device("n", {"host": "h", "transport": "ws"}, mock.Mock())
        self.assertIsInstance(d, shelly.ShellyWsDevice)

    def test_http_fallback_when_websocket_missing(self):
        log = mock.Mock()
        with mock.patch.object(shelly, "websocket", None):
            d = shelly.make_device("n", {"host": "h", "transport": "ws"}, log)
        self.assertIsInstance(d, shelly.ShellyHttpDevice)
        log.warning.assert_called()

    def test_http_requested(self):
        d = shelly.make_device("n", {"host": "h", "transport": "http"}, mock.Mock())
        self.assertIsInstance(d, shelly.ShellyHttpDevice)


if __name__ == "__main__":
    unittest.main()
