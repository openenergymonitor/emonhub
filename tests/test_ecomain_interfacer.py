import importlib
import subprocess
import sys
import textwrap
import unittest
import warnings
from unittest.mock import MagicMock, call, patch

from configobj import ConfigObj

import interfacers
import emonhub_coder as ehc
from interfacers.EmonHubEcoMainInterfacer import (
    EcoMainConfigError,
    EcoMainReadError,
    EmonHubEcoMainInterfacer,
    SINGLE_PHASE_NAMES,
    THREE_PHASE_NAMES,
    _apply_invert,
    _build_single_phase_cargo,
    _build_three_phase_cargo,
    _parse_meters,
    _parse_phase,
)
from interfacers.EmonHubMqttInterfacer import EmonHubMqttInterfacer


EXPECTED_SERIAL = "001234567890"


class InterfacerRegistrationTests(unittest.TestCase):
    def test_ecomain_type_is_registered_and_importable(self):
        type_name = "EmonHubEcoMainInterfacer"

        self.assertIn(type_name, interfacers.__all__)
        module = importlib.import_module(f"interfacers.{type_name}")
        self.assertEqual(getattr(module, type_name).__name__, type_name)

    def test_module_import_succeeds_without_pymodbus(self):
        script = textwrap.dedent(
            """
            import builtins
            import importlib

            original_import = builtins.__import__

            def block_pymodbus(name, *args, **kwargs):
                if name == "pymodbus" or name.startswith("pymodbus."):
                    raise ImportError("pymodbus intentionally unavailable")
                return original_import(name, *args, **kwargs)

            builtins.__import__ = block_pymodbus
            module = importlib.import_module(
                "interfacers.EmonHubEcoMainInterfacer"
            )
            assert module.ModbusTcpClient is None
            """
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_module_import_supports_legacy_pymodbus_client_path(self):
        script = textwrap.dedent(
            """
            import importlib
            import sys
            import types

            pymodbus = types.ModuleType("pymodbus")
            pymodbus.__path__ = []
            client = types.ModuleType("pymodbus.client")
            client.__path__ = []
            sync = types.ModuleType("pymodbus.client.sync")

            class LegacyModbusTcpClient:
                pass

            sync.ModbusTcpClient = LegacyModbusTcpClient
            sys.modules["pymodbus"] = pymodbus
            sys.modules["pymodbus.client"] = client
            sys.modules["pymodbus.client.sync"] = sync

            module = importlib.import_module(
                "interfacers.EmonHubEcoMainInterfacer"
            )
            assert module.ModbusTcpClient is LegacyModbusTcpClient
            """
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


def valid_meters():
    return {
        "grid": {
            "nodeid": "30",
            "nodename": "ecomain_grid",
            "source": "grid",
        },
        "heatpump": {
            "nodeid": "31",
            "nodename": "ecomain_heatpump",
            "source": "branches",
            "phases": "1:4:true",
        },
    }


def make_driver(**kwargs):
    kwargs.setdefault("serial", EXPECTED_SERIAL)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"setName\(\) is deprecated, set the name attribute instead",
            category=DeprecationWarning,
        )
        return EmonHubEcoMainInterfacer("EcoMain", **kwargs)


def device_info(model="2401", software=139, serial=EXPECTED_SERIAL):
    return {
        "model": model,
        "serial": serial,
        "versions": {
            "hardware": 1,
            "ecomain_software": software,
            "ecomain_firmware": 139,
            "ecosub_1_firmware": 0,
            "ecosub_2_firmware": 0,
            "ecosub_3_firmware": 0,
        },
    }


def branch_sample(power):
    return {
        "power": power,
        "energy": power + 1.0,
        "return_energy": power + 2.0,
        "voltage": 230.0,
        "current": 1.0,
        "power_factor": 0.9,
    }


def branch_device(base):
    return {channel: branch_sample(base + channel) for channel in range(1, 11)}


def grid_sample():
    return {
        "power": 60.0,
        "energy": 100.0,
        "return_energy": 2.0,
        "phases": [
            {
                "power": 10.0,
                "voltage": 230.0,
                "current": 1.0,
                "power_factor": 0.91,
            },
            {
                "power": 20.0,
                "voltage": 231.0,
                "current": 2.0,
                "power_factor": 0.92,
            },
            {
                "power": 30.0,
                "voltage": 232.0,
                "current": 3.0,
                "power_factor": 0.93,
            },
        ],
    }


def branch_meters():
    return {
        "first": {
            "nodeid": "41",
            "nodename": "first",
            "source": "branches",
            "phases": "0:1:false",
        },
        "second": {
            "nodeid": "42",
            "nodename": "second",
            "source": "branches",
            "phases": "0:2:false",
        },
        "third": {
            "nodeid": "43",
            "nodename": "third",
            "source": "branches",
            "phases": "2:1:false",
        },
    }


class PhaseParsingTests(unittest.TestCase):
    def test_phase_parses_explicit_false(self):
        self.assertEqual(
            _parse_phase("0:1:false"),
            {"device": 0, "channel": 1, "invert": False},
        )

    def test_phase_boolean_is_case_insensitive_but_not_ambiguous(self):
        self.assertTrue(_parse_phase("3:10:TrUe")["invert"])
        for value in ("yes", "no", "1", "0", "on", "off", ""):
            with self.subTest(value=value):
                with self.assertRaises(EcoMainConfigError):
                    _parse_phase(f"0:1:{value}")

    def test_phase_requires_exactly_three_fields(self):
        for value in ("0:1", "0:1:false:extra"):
            with self.subTest(value=value):
                with self.assertRaises(EcoMainConfigError):
                    _parse_phase(value)

    def test_phase_rejects_device_and_channel_outside_supported_ranges(self):
        for value in ("-1:1:false", "4:1:false", "0:0:false", "0:11:false"):
            with self.subTest(value=value):
                with self.assertRaises(EcoMainConfigError):
                    _parse_phase(value)


class MeterParsingTests(unittest.TestCase):
    def test_empty_meters_are_rejected(self):
        with self.assertRaises(EcoMainConfigError):
            _parse_meters({})

    def test_grid_rejects_phases_and_only_one_grid_is_allowed(self):
        with self.assertRaises(EcoMainConfigError):
            _parse_meters(
                {
                    "grid": {
                        "nodeid": "1",
                        "nodename": "grid",
                        "source": "grid",
                        "phases": "0:1:false",
                    }
                }
            )

        with self.assertRaises(EcoMainConfigError):
            _parse_meters(
                {
                    "grid_a": {
                        "nodeid": "1",
                        "nodename": "grid_a",
                        "source": "grid",
                    },
                    "grid_b": {
                        "nodeid": "2",
                        "nodename": "grid_b",
                        "source": "grid",
                    },
                }
            )

    def test_branches_require_exactly_one_or_three_phases(self):
        for phases in (None, [], ["0:1:false", "0:2:false"]):
            meter = {
                "nodeid": "1",
                "nodename": "load",
                "source": "branches",
            }
            if phases is not None:
                meter["phases"] = phases
            with self.subTest(phases=phases):
                with self.assertRaises(EcoMainConfigError):
                    _parse_meters({"load": meter})

    def test_branches_reject_mapping_shaped_phases(self):
        with self.assertRaises(EcoMainConfigError):
            _parse_meters(
                {
                    "load": {
                        "nodeid": "1",
                        "nodename": "load",
                        "source": "branches",
                        "phases": {"0:1:false": "ignored"},
                    }
                }
            )

    def test_source_must_be_grid_or_branches(self):
        with self.assertRaises(EcoMainConfigError):
            _parse_meters(
                {
                    "load": {
                        "nodeid": "1",
                        "nodename": "load",
                        "source": "branch",
                        "phases": "0:1:false",
                    }
                }
            )

    def test_nodeid_must_be_an_integer_and_globally_unique(self):
        with self.assertRaises(EcoMainConfigError):
            _parse_meters(
                {
                    "load": {
                        "nodeid": "1.5",
                        "nodename": "load",
                        "source": "branches",
                        "phases": "0:1:false",
                    }
                }
            )

        meters = valid_meters()
        meters["heatpump"]["nodeid"] = "30"
        with self.assertRaises(EcoMainConfigError):
            _parse_meters(meters)

    def test_nodename_must_be_nonempty_and_globally_unique(self):
        for nodename in (None, "", "   "):
            with self.subTest(nodename=nodename):
                with self.assertRaises(EcoMainConfigError):
                    _parse_meters(
                        {
                            "load": {
                                "nodeid": "1",
                                "nodename": nodename,
                                "source": "branches",
                                "phases": "0:1:false",
                            }
                        }
                    )

        meters = valid_meters()
        meters["heatpump"]["nodename"] = "ecomain_grid"
        with self.assertRaises(EcoMainConfigError):
            _parse_meters(meters)

    def test_nodename_rejects_mqtt_or_emoncms_unsafe_characters(self):
        for nodename in (
            "ecomain/grid",
            "ecomain#grid",
            "ecomain+grid",
            "ecomain:grid",
        ):
            with self.subTest(nodename=nodename):
                with self.assertRaisesRegex(
                    EcoMainConfigError, "contains unsupported characters"
                ):
                    _parse_meters(
                        {
                            "grid": {
                                "nodeid": "30",
                                "nodename": nodename,
                                "source": "grid",
                            }
                        }
                    )

        parsed = _parse_meters(
            {
                "grid": {
                    "nodeid": "30",
                    "nodename": "ecoMain 测试-1.0",
                    "source": "grid",
                }
            }
        )
        self.assertEqual(parsed[0]["nodename"], "ecoMain 测试-1.0")

    def test_branch_reference_is_globally_unique(self):
        for meters in (
            {
                "load": {
                    "nodeid": "1",
                    "nodename": "load",
                    "source": "branches",
                    "phases": ["0:1:false", "0:1:true", "0:2:false"],
                }
            },
            {
                "load_a": {
                    "nodeid": "1",
                    "nodename": "load_a",
                    "source": "branches",
                    "phases": "0:1:false",
                },
                "load_b": {
                    "nodeid": "2",
                    "nodename": "load_b",
                    "source": "branches",
                    "phases": "0:1:true",
                },
            },
        ):
            with self.subTest(meters=meters):
                with self.assertRaises(EcoMainConfigError):
                    _parse_meters(meters)

    def test_parsed_meters_preserve_configobj_insertion_order(self):
        meters = ConfigObj()
        meters["heatpump"] = {
            "nodeid": "31",
            "nodename": "ecomain_heatpump",
            "source": "branches",
            "phases": "1:4:true",
        }
        meters["grid"] = {
            "nodeid": "30",
            "nodename": "ecomain_grid",
            "source": "grid",
        }

        parsed = _parse_meters(meters)

        self.assertIsInstance(parsed, tuple)
        self.assertEqual([meter["name"] for meter in parsed], ["heatpump", "grid"])
        self.assertEqual(
            parsed[0],
            {
                "name": "heatpump",
                "nodeid": 31,
                "nodename": "ecomain_heatpump",
                "source": "branches",
                "phases": (
                    {"device": 1, "channel": 4, "invert": True},
                ),
            },
        )

    def test_configobj_three_phase_list_is_applied_end_to_end(self):
        config = ConfigObj(
            [
                "[meters]",
                "[[pv]]",
                "nodeid = 31",
                "nodename = ecomain_pv",
                "source = branches",
                "phases = 0:1:false, 0:2:false, 0:3:false",
            ]
        )
        driver = make_driver(host="meter.local")

        driver.set(meters=config["meters"])

        self.assertEqual(
            driver._meters[0]["phases"],
            (
                {"device": 0, "channel": 1, "invert": False},
                {"device": 0, "channel": 2, "invert": False},
                {"device": 0, "channel": 3, "invert": False},
            ),
        )


class CargoMappingTests(unittest.TestCase):
    def test_invert_reverses_direction_without_changing_electrical_values(self):
        sample = {
            "power": 125.5,
            "energy": 8.0,
            "return_energy": 1.25,
            "voltage": 231.2,
            "current": 0.75,
            "power_factor": 0.92,
        }

        result = _apply_invert(sample, True)

        self.assertEqual(
            result,
            {
                "power": -125.5,
                "energy": 1.25,
                "return_energy": 8.0,
                "voltage": 231.2,
                "current": 0.75,
                "power_factor": -0.92,
            },
        )
        self.assertEqual(sample["power"], 125.5)
        self.assertIsNot(_apply_invert(sample, False), sample)

    def test_single_phase_cargo_has_fixed_schema_and_metadata(self):
        meter = {"nodeid": 31, "nodename": "ecomain_heatpump"}
        sample = {
            "power": 0.0,
            "energy": 12.5,
            "return_energy": 0.25,
            "voltage": 230.0,
            "current": 0.0,
            "power_factor": 0.0,
        }

        cargo = _build_single_phase_cargo(meter, sample, 1725181200.25)

        self.assertEqual(cargo.nodeid, 31)
        self.assertEqual(cargo.nodename, "ecomain_heatpump")
        self.assertEqual(cargo.names, list(SINGLE_PHASE_NAMES))
        self.assertEqual(
            cargo.names,
            [
                "power",
                "energy",
                "return_energy",
                "voltage",
                "current",
                "power_factor",
            ],
        )
        self.assertEqual(cargo.realdata, [0.0, 12.5, 0.25, 230.0, 0.0, 0.0])
        self.assertEqual(cargo.timestamp, 1725181200.25)

    def test_three_phase_branch_aggregates_post_invert_samples_and_keeps_zeros(self):
        meter = {"nodeid": 32, "nodename": "ecomain_branch"}
        phases = [
            {
                "power": 100.0,
                "energy": 10.0,
                "return_energy": 1.0,
                "voltage": 230.0,
                "current": 1.0,
                "power_factor": 0.9,
            },
            _apply_invert(
                {
                    "power": 40.0,
                    "energy": 7.0,
                    "return_energy": 2.0,
                    "voltage": 231.0,
                    "current": 0.0,
                    "power_factor": 0.8,
                },
                True,
            ),
            {
                "power": 0.0,
                "energy": 3.0,
                "return_energy": 0.5,
                "voltage": 229.0,
                "current": 0.0,
                "power_factor": 0.0,
            },
        ]

        cargo = _build_three_phase_cargo(meter, phases, 1725181201.5)

        self.assertEqual(cargo.nodeid, 32)
        self.assertEqual(cargo.nodename, "ecomain_branch")
        self.assertEqual(cargo.names, list(THREE_PHASE_NAMES))
        self.assertEqual(
            cargo.names,
            [
                "power",
                "energy",
                "return_energy",
                "power_l1",
                "power_l2",
                "power_l3",
                "voltage_l1",
                "voltage_l2",
                "voltage_l3",
                "current_l1",
                "current_l2",
                "current_l3",
                "power_factor_l1",
                "power_factor_l2",
                "power_factor_l3",
            ],
        )
        self.assertEqual(
            cargo.realdata,
            [
                60.0,
                15.0,
                8.5,
                100.0,
                -40.0,
                0.0,
                230.0,
                231.0,
                229.0,
                1.0,
                0.0,
                0.0,
                0.9,
                -0.8,
                0.0,
            ],
        )
        self.assertEqual(len(cargo.names), 15)
        self.assertEqual(len(cargo.realdata), 15)
        self.assertEqual(cargo.timestamp, 1725181201.5)

    def test_grid_cargo_preserves_protocol_totals_and_phase_order(self):
        meter = {"nodeid": 30, "nodename": "ecomain_grid"}
        phases = [
            {"power": 10.0, "voltage": 230.0, "current": 1.0, "power_factor": 0.91},
            {"power": 20.0, "voltage": 231.0, "current": 2.0, "power_factor": 0.92},
            {"power": 30.0, "voltage": 232.0, "current": 3.0, "power_factor": 0.93},
        ]
        totals = {"power": 123.0, "energy": 456.0, "return_energy": 7.0}

        cargo = _build_three_phase_cargo(
            meter, phases, 1725181202.75, totals=totals
        )

        self.assertEqual(cargo.nodeid, 30)
        self.assertEqual(cargo.nodename, "ecomain_grid")
        self.assertEqual(cargo.names, list(THREE_PHASE_NAMES))
        self.assertEqual(
            cargo.realdata,
            [
                123.0,
                456.0,
                7.0,
                10.0,
                20.0,
                30.0,
                230.0,
                231.0,
                232.0,
                1.0,
                2.0,
                3.0,
                0.91,
                0.92,
                0.93,
            ],
        )
        self.assertEqual(cargo.timestamp, 1725181202.75)

    def test_three_phase_cargo_rejects_two_phase_samples(self):
        meter = {"nodeid": 32, "nodename": "ecomain_branch"}
        phase = {
            "power": 10.0,
            "energy": 1.0,
            "return_energy": 0.0,
            "voltage": 230.0,
            "current": 1.0,
            "power_factor": 0.9,
        }

        with self.assertRaisesRegex(
            EcoMainConfigError, "three-phase cargo requires exactly three phases"
        ):
            _build_three_phase_cargo(meter, [phase, phase], 1725181203.0)

    def test_three_phase_cargo_rejects_four_phase_samples(self):
        meter = {"nodeid": 32, "nodename": "ecomain_branch"}
        phase = {
            "power": 10.0,
            "energy": 1.0,
            "return_energy": 0.0,
            "voltage": 230.0,
            "current": 1.0,
            "power_factor": 0.9,
        }

        with self.assertRaisesRegex(
            EcoMainConfigError, "three-phase cargo requires exactly three phases"
        ):
            _build_three_phase_cargo(meter, [phase, phase, phase, phase], 1725181203.0)


class DataFlowIntegrationTests(unittest.TestCase):
    def _read_two_meters(self):
        driver = make_driver(host="meter.local")
        driver.set(meters=valid_meters())
        driver._client = MagicMock()
        driver._reader = MagicMock()
        driver._reader.read_grid.return_value = grid_sample()
        driver._reader.read_branch_device.return_value = branch_device(10.0)

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            side_effect=[1725181300.25, 1725181300.5],
        ):
            first = driver.read()
        second = driver.read()
        return driver, first, second

    def test_process_rx_preserves_each_logical_meter_metadata(self):
        driver, first, second = self._read_two_meters()
        original = [
            (
                cargo.nodeid,
                cargo.nodename,
                list(cargo.names),
                list(cargo.realdata),
                cargo.timestamp,
            )
            for cargo in (first, second)
        ]

        with patch.object(
            ehc,
            "nodelist",
            {
                "30": {"nodename": "global_grid"},
                "31": {"nodename": "global_heatpump"},
            },
        ):
            processed = [driver._process_rx(first), driver._process_rx(second)]

        self.assertEqual(
            [
                (
                    cargo.nodeid,
                    cargo.nodename,
                    cargo.names,
                    cargo.realdata,
                    cargo.timestamp,
                )
                for cargo in processed
            ],
            original,
        )

    def test_processed_cargo_uses_nodename_in_real_mqtt_topics(self):
        driver, first, second = self._read_two_meters()
        with patch.object(ehc, "nodelist", {}):
            processed = [driver._process_rx(first), driver._process_rx(second)]

        with patch(
            "interfacers.EmonHubMqttInterfacer.mqtt.Client"
        ) as client_class, warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"setName\(\) is deprecated, set the name attribute instead",
                category=DeprecationWarning,
            )
            mqtt_interfacer = EmonHubMqttInterfacer("MQTT")
        mqtt_interfacer._connected = True
        mqtt_interfacer.set(
            node_format_enable=0,
            nodevar_format_enable=1,
            nodevar_format_basetopic="emon/",
            node_JSON_enable=0,
        )
        mqtt_client = client_class.return_value
        mqtt_client.publish.return_value = (0, 1)

        for cargo in processed:
            mqtt_interfacer.add(cargo)

        topics_and_payloads = [
            (entry.args[0], entry.kwargs["payload"])
            for entry in mqtt_client.publish.call_args_list
        ]
        self.assertEqual(
            topics_and_payloads,
            [
                ("emon/ecomain_grid/power", "60"),
                ("emon/ecomain_grid/energy", "100"),
                ("emon/ecomain_grid/return_energy", "2"),
                ("emon/ecomain_grid/power_l1", "10"),
                ("emon/ecomain_grid/power_l2", "20"),
                ("emon/ecomain_grid/power_l3", "30"),
                ("emon/ecomain_grid/voltage_l1", "230"),
                ("emon/ecomain_grid/voltage_l2", "231"),
                ("emon/ecomain_grid/voltage_l3", "232"),
                ("emon/ecomain_grid/current_l1", "1"),
                ("emon/ecomain_grid/current_l2", "2"),
                ("emon/ecomain_grid/current_l3", "3"),
                ("emon/ecomain_grid/power_factor_l1", "0.91"),
                ("emon/ecomain_grid/power_factor_l2", "0.92"),
                ("emon/ecomain_grid/power_factor_l3", "0.93"),
                ("emon/ecomain_heatpump/power", "-14"),
                ("emon/ecomain_heatpump/energy", "16"),
                ("emon/ecomain_heatpump/return_energy", "15"),
                ("emon/ecomain_heatpump/voltage", "230"),
                ("emon/ecomain_heatpump/current", "1"),
                ("emon/ecomain_heatpump/power_factor", "-0.9"),
            ],
        )


class InterfacerConfigurationTests(unittest.TestCase):
    def test_constructor_exposes_only_device_specific_connection_settings(self):
        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient"
        ) as client_class:
            driver = make_driver(
                host="meter.local", serial="001234567890", timeout="2.5"
            )

        client_class.assert_not_called()
        self.assertEqual(
            driver.init_settings,
            {
                "host": "meter.local",
                "serial": "001234567890",
                "timeout": 2.5,
            },
        )
        self.assertIsNone(driver._client)
        self.assertIsNone(driver._reader)

    def test_serial_must_contain_exactly_twelve_digits(self):
        invalid_serials = (
            None,
            "",
            "00123456789",
            "0012345678900",
            "00123456789A",
        )
        for serial in invalid_serials:
            with self.subTest(serial=serial), self.assertLogs(
                "EmonHub", level="WARNING"
            ):
                driver = make_driver(host="meter.local", serial=serial)
                self.assertIsNone(driver._connection_settings)

        driver = make_driver(host="meter.local", serial="001234567890")
        self.assertEqual(driver.init_settings["serial"], "001234567890")

    def test_loader_raw_init_settings_do_not_replace_typed_connection_state(self):
        config = ConfigObj(
            [
                "[ecoMain]",
                "Type = EmonHubEcoMainInterfacer",
                "[[init_settings]]",
                "host = meter.local",
                f"serial = {EXPECTED_SERIAL}",
                "timeout = 2.5",
                "[[runtimesettings]]",
                "read_interval = 10",
                "[[[meters]]]",
                "[[[[grid]]]]",
                "nodeid = 30",
                "nodename = ecomain_grid",
                "source = grid",
            ]
        )
        settings = config["ecoMain"]
        driver = make_driver(**settings["init_settings"])
        driver.set(**settings["runtimesettings"])
        driver.init_settings = settings["init_settings"]
        client = MagicMock()
        client.connect.return_value = True
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_grid.return_value = grid_sample()
        reader.read_branch_device.return_value = branch_device(10.0)

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            return_value=client,
        ) as client_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ) as reader_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            side_effect=[100.0, 100.0],
        ):
            cargo = driver.read()

        self.assertEqual(cargo.nodeid, 30)
        client_class.assert_called_once_with(
            host="meter.local", port=502, timeout=2.5
        )
        reader_class.assert_called_once_with(client, unit_id=255)

    def test_invalid_physical_settings_remain_idle_without_connecting(self):
        invalid_settings = (
            {"host": ""},
            {"host": "   "},
            {"host": None},
            {"host": "meter.local", "timeout": "not-a-timeout"},
            {"host": "meter.local", "timeout": "nan"},
            {"host": "meter.local", "timeout": "inf"},
            {"host": "meter.local", "timeout": "-inf"},
            {"host": "meter.local", "timeout": 0},
            {"host": "meter.local", "timeout": -1},
        )

        for settings in invalid_settings:
            with self.subTest(settings=settings), self.assertLogs(
                "EmonHub", level="WARNING"
            ):
                try:
                    driver = make_driver(**settings)
                except Exception as exc:
                    self.fail(f"invalid physical settings raised {exc!r}")
                driver.set(meters=valid_meters())
                with patch(
                    "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient"
                ) as client_class, patch(
                    "interfacers.EmonHubEcoMainInterfacer.current_time",
                    return_value=100.0,
                ) as current_time:
                    result = driver.read()

                self.assertIsNone(result)
                client_class.assert_not_called()
                current_time.assert_not_called()

    def test_valid_runtime_settings_are_applied_with_parent_settings(self):
        driver = make_driver()

        driver.set(
            read_interval="10",
            meters=valid_meters(),
            pubchannels=["ToEmonCMS"],
        )

        self.assertEqual(driver._settings["read_interval"], 10.0)
        self.assertEqual(driver._settings["pubchannels"], ["ToEmonCMS"])
        self.assertEqual([meter["name"] for meter in driver._meters], ["grid", "heatpump"])

    def test_invalid_runtime_settings_preserve_the_previous_snapshot(self):
        driver = make_driver()
        driver.set(
            read_interval="10",
            meters=valid_meters(),
            pubchannels=["ToEmonCMS"],
        )
        previous = driver._meters
        invalid_meters = valid_meters()
        invalid_meters["heatpump"]["phases"] = "4:1:false"

        with self.assertLogs("EmonHub", level="WARNING"):
            driver.set(
                read_interval="bad",
                meters=invalid_meters,
                pubchannels=["Changed"],
            )

        self.assertIs(driver._meters, previous)
        self.assertEqual(driver._settings["read_interval"], 10.0)
        self.assertEqual(driver._settings["pubchannels"], ["ToEmonCMS"])

    def test_empty_meter_update_preserves_all_runtime_state_and_pending_cargo(self):
        driver = make_driver(host="meter.local")
        driver.set(
            read_interval="10",
            meters=valid_meters(),
            pubchannels=["ToEmonCMS"],
        )
        previous_meters = driver._meters
        pending = MagicMock()
        driver._pending.append(pending)

        with self.assertLogs("EmonHub", level="WARNING"):
            driver.set(
                read_interval="20",
                meters={},
                pubchannels=["Changed"],
            )

        self.assertIs(driver._meters, previous_meters)
        self.assertEqual(driver._settings["read_interval"], 10.0)
        self.assertEqual(driver._settings["pubchannels"], ["ToEmonCMS"])
        self.assertEqual(list(driver._pending), [pending])

    def test_valid_meter_update_discards_pending_cargo_from_old_snapshot(self):
        driver = make_driver(host="meter.local")
        driver.set(meters=valid_meters())
        driver._pending.extend([MagicMock(), MagicMock()])
        replacement = {
            "renamed": {
                "nodeid": "50",
                "nodename": "renamed",
                "source": "branches",
                "phases": "0:1:false",
            }
        }

        driver.set(meters=replacement)

        self.assertEqual([meter["name"] for meter in driver._meters], ["renamed"])
        self.assertEqual(list(driver._pending), [])

    def test_read_interval_must_be_finite_and_positive(self):
        driver = make_driver()
        driver.set(read_interval="10", meters=valid_meters())
        previous = driver._meters

        for value in ("nan", "inf", "-inf", "0", "-1"):
            with self.subTest(value=value):
                with self.assertLogs("EmonHub", level="WARNING"):
                    driver.set(read_interval=value, meters={})
                self.assertIs(driver._meters, previous)
                self.assertEqual(driver._settings["read_interval"], 10.0)


class DeviceIdentityTests(unittest.TestCase):
    def _connect_with_info(self, info):
        driver = make_driver(
            host="meter.local", serial=EXPECTED_SERIAL, timeout=2.5
        )
        client = MagicMock()
        client.connect.return_value = True
        reader = MagicMock()
        reader.read_device_info.return_value = info

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            return_value=client,
        ) as client_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ) as reader_class:
            connected = driver._connect()

        return driver, client, reader, client_class, reader_class, connected

    def test_valid_identity_uses_fixed_transport_and_supported_software(self):
        for software in (139, 140):
            with self.subTest(software=software):
                driver, client, _, client_class, reader_class, connected = (
                    self._connect_with_info(device_info(software=software))
                )

                self.assertTrue(connected)
                client_class.assert_called_once_with(
                    host="meter.local", port=502, timeout=2.5
                )
                reader_class.assert_called_once_with(client, unit_id=255)
                self.assertIs(driver._client, client)

    def test_identity_validation_stops_at_first_failed_check(self):
        cases = (
            (
                device_info(model="2501", software=138, serial="001234567891"),
                "unexpected model",
            ),
            (
                device_info(software=138, serial="001234567891"),
                "unsupported software version",
            ),
            (device_info(serial="001234567891"), "serial number mismatch"),
        )

        for info, message in cases:
            with self.subTest(message=message), self.assertLogs(
                "EmonHub", level="WARNING"
            ) as logs:
                driver, client, _, _, _, connected = self._connect_with_info(info)

            self.assertFalse(connected)
            self.assertTrue(any(message in entry for entry in logs.output))
            client.close.assert_called_once_with()
            self.assertIsNone(driver._client)
            self.assertIsNone(driver._reader)

    def test_invalid_identity_never_reads_or_publishes_measurements(self):
        driver = make_driver(host="meter.local", serial=EXPECTED_SERIAL)
        driver.set(meters=valid_meters())
        client = MagicMock()
        client.connect.return_value = True
        reader = MagicMock()
        reader.read_device_info.return_value = device_info(model="2501")

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            return_value=client,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            side_effect=[100.0, 100.0],
        ), self.assertLogs("EmonHub", level="WARNING"):
            cargo = driver.read()

        self.assertIsNone(cargo)
        reader.read_grid.assert_not_called()
        reader.read_branch_device.assert_not_called()
        client.close.assert_called_once_with()
        self.assertEqual(driver._failure_count, 1)
        self.assertEqual(driver._next_poll_at, 110.0)


class InterfacerPollingTests(unittest.TestCase):
    def setUp(self):
        self.driver = make_driver(host="meter.local", timeout=2.5)

    def test_first_due_read_connects_lazily_and_reads_device_info_once(self):
        self.driver.set(meters=valid_meters())
        client = MagicMock()
        client.connect.return_value = True
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_grid.return_value = grid_sample()
        reader.read_branch_device.return_value = branch_device(10.0)

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            return_value=client,
        ) as client_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ) as reader_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            return_value=100.0,
        ), self.assertLogs("EmonHub", level="INFO") as logs:
            first = self.driver.read()
            second = self.driver.read()

        client_class.assert_called_once_with(
            host="meter.local", port=502, timeout=2.5
        )
        client.connect.assert_called_once_with()
        reader_class.assert_called_once_with(client, unit_id=255)
        reader.read_device_info.assert_called_once_with()
        self.assertTrue(
            any("EcoMain" in line and EXPECTED_SERIAL in line for line in logs.output)
        )
        self.assertEqual(first.nodeid, 30)
        self.assertEqual(second.nodeid, 31)
        self.assertEqual(first.timestamp, 100.0)
        self.assertEqual(second.timestamp, 100.0)
        reader.read_grid.assert_called_once_with()
        reader.read_branch_device.assert_called_once_with(1)

    def test_pending_cargo_is_drained_before_clock_or_network_access(self):
        self.driver.set(meters=valid_meters())
        pending = MagicMock()
        self.driver._pending.append(pending)

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time"
        ) as current_time, patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient"
        ) as client_class:
            result = self.driver.read()

        self.assertIs(result, pending)
        current_time.assert_not_called()
        client_class.assert_not_called()

    def test_read_before_deadline_is_idle_without_sleep_or_network(self):
        self.driver.set(meters=valid_meters())
        self.driver._next_poll_at = 101.0

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time", return_value=100.0
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.time.sleep",
            side_effect=AssertionError("read must not sleep"),
        ) as sleeper, patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient"
        ) as client_class:
            result = self.driver.read()

        self.assertIsNone(result)
        sleeper.assert_not_called()
        client_class.assert_not_called()

    def test_poll_reads_only_ordered_unique_sources(self):
        meters = branch_meters()
        meters["grid"] = {
            "nodeid": "44",
            "nodename": "grid",
            "source": "grid",
        }
        self.driver.set(meters=meters)
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_branch_device.side_effect = [
            branch_device(10.0),
            branch_device(20.0),
        ]
        reader.read_grid.return_value = grid_sample()

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient"
        ) as client_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time", return_value=100.0
        ):
            client_class.return_value.connect.return_value = True
            cargos = [self.driver.read() for _ in range(4)]

        self.assertEqual([cargo.nodeid for cargo in cargos], [41, 42, 43, 44])
        self.assertEqual(
            reader.mock_calls,
            [
                call.read_device_info(),
                call.read_branch_device(0),
                call.read_branch_device(2),
                call.read_grid(),
            ],
        )

    def test_branch_selection_and_invert_are_reflected_in_final_realdata(self):
        self.driver.set(
            meters={
                "inverted": {
                    "nodeid": "45",
                    "nodename": "inverted",
                    "source": "branches",
                    "phases": "2:4:true",
                }
            }
        )
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_branch_device.return_value = branch_device(20.0)

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient"
        ) as client_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            return_value=100.0,
        ):
            client_class.return_value.connect.return_value = True
            cargo = self.driver.read()

        reader.read_branch_device.assert_called_once_with(2)
        self.assertEqual(cargo.names, list(SINGLE_PHASE_NAMES))
        self.assertEqual(cargo.realdata, [-24.0, 26.0, 25.0, 230.0, 1.0, -0.9])

    def test_device_info_failure_blocks_measurements(self):
        self.driver.set(meters=valid_meters())
        reader = MagicMock()
        reader.read_device_info.side_effect = RuntimeError("info unavailable")
        reader.read_grid.return_value = grid_sample()
        reader.read_branch_device.return_value = branch_device(10.0)

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient"
        ) as client_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time", return_value=100.0
        ), self.assertLogs("EmonHub", level="WARNING"):
            client_class.return_value.connect.return_value = True
            cargo = self.driver.read()

        self.assertIsNone(cargo)
        reader.read_grid.assert_not_called()
        client_class.return_value.close.assert_called_once_with()

    def test_close_is_idempotent_and_clears_connection_state(self):
        client = MagicMock()
        self.driver._client = client
        self.driver._reader = MagicMock()

        self.driver.close()
        self.driver.close()

        client.close.assert_called_once_with()
        self.assertIsNone(self.driver._client)
        self.assertIsNone(self.driver._reader)


class InterfacerFailureTests(unittest.TestCase):
    def setUp(self):
        self.driver = make_driver(host="meter.local")

    def _read_with(self, now, reader, connect_result=True):
        client = MagicMock()
        client.connect.return_value = connect_result
        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            return_value=client,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time", return_value=now
        ):
            result = self.driver.read()
        return result, client

    def test_failure_publishes_only_meters_completed_before_failed_group(self):
        self.driver.set(meters=branch_meters())
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_branch_device.side_effect = [
            branch_device(10.0),
            EcoMainReadError("device 2 failed"),
        ]

        first, client = self._read_with(100.0, reader)
        second = self.driver.read()

        self.assertEqual(first.nodeid, 41)
        self.assertEqual(second.nodeid, 42)
        self.assertEqual(first.timestamp, 100.0)
        self.assertEqual(second.timestamp, 100.0)
        self.assertEqual(reader.read_branch_device.call_args_list, [call(0), call(2)])
        client.close.assert_called_once_with()
        self.assertIsNone(self.driver._client)
        self.assertIsNone(self.driver._reader)
        self.assertEqual(self.driver._failure_count, 1)
        self.assertEqual(self.driver._next_poll_at, 110.0)

    def test_failure_skips_partial_meter_and_stops_before_later_source(self):
        self.driver.set(
            meters={
                "complete": {
                    "nodeid": "41",
                    "nodename": "complete",
                    "source": "branches",
                    "phases": "0:1:false",
                },
                "spanning": {
                    "nodeid": "42",
                    "nodename": "spanning",
                    "source": "branches",
                    "phases": [
                        "0:2:false",
                        "1:1:false",
                        "1:2:false",
                    ],
                },
                "later": {
                    "nodeid": "43",
                    "nodename": "later",
                    "source": "branches",
                    "phases": "3:1:false",
                },
            }
        )
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_branch_device.side_effect = [
            branch_device(10.0),
            EcoMainReadError("device 1 failed"),
            branch_device(30.0),
        ]

        first, _ = self._read_with(100.0, reader)

        self.assertEqual(first.nodeid, 41)
        self.assertEqual(list(self.driver._pending), [])
        self.assertEqual(reader.read_branch_device.call_args_list, [call(0), call(1)])

    def test_poll_reconnects_after_backoff_with_fresh_info_and_measurements(self):
        self.driver.set(
            meters={
                "load": {
                    "nodeid": "41",
                    "nodename": "load",
                    "source": "branches",
                    "phases": "0:1:false",
                }
            }
        )
        first_client = MagicMock()
        first_client.connect.return_value = True
        second_client = MagicMock()
        second_client.connect.return_value = True
        first_reader = MagicMock()
        first_reader.read_device_info.return_value = device_info()
        first_reader.read_branch_device.side_effect = EcoMainReadError("offline")
        second_reader = MagicMock()
        second_reader.read_device_info.return_value = device_info()
        second_reader.read_branch_device.return_value = branch_device(20.0)

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            side_effect=[first_client, second_client],
        ) as client_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            side_effect=[first_reader, second_reader],
        ) as reader_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            side_effect=[100.0, 100.0, 111.0, 111.0],
        ):
            failed = self.driver.read()
            recovered = self.driver.read()

        self.assertIsNone(failed)
        self.assertEqual(recovered.nodeid, 41)
        self.assertEqual(recovered.timestamp, 111.0)
        self.assertEqual(recovered.realdata[0], 21.0)
        self.assertEqual(client_class.call_count, 2)
        self.assertEqual(
            reader_class.call_args_list,
            [call(first_client, unit_id=255), call(second_client, unit_id=255)],
        )
        first_reader.read_device_info.assert_called_once_with()
        second_reader.read_device_info.assert_called_once_with()
        first_reader.read_branch_device.assert_called_once_with(0)
        second_reader.read_branch_device.assert_called_once_with(0)
        first_client.close.assert_called_once_with()
        self.assertIs(self.driver._client, second_client)
        self.assertIs(self.driver._reader, second_reader)
        self.assertEqual(self.driver._failure_count, 0)
        self.assertEqual(self.driver._next_poll_at, 121.0)

    def test_failed_group_never_reuses_a_previous_poll_sample(self):
        meters = {
            "load": {
                "nodeid": "41",
                "nodename": "load",
                "source": "branches",
                "phases": "0:1:false",
            }
        }
        self.driver.set(read_interval=1, meters=meters)
        successful_reader = MagicMock()
        successful_reader.read_device_info.return_value = device_info()
        successful_reader.read_branch_device.return_value = branch_device(10.0)
        first, _ = self._read_with(100.0, successful_reader)
        self.driver._disconnect()
        failing_reader = MagicMock()
        failing_reader.read_device_info.return_value = device_info()
        failing_reader.read_branch_device.side_effect = EcoMainReadError("failed")

        second, _ = self._read_with(101.0, failing_reader)

        self.assertEqual(first.nodeid, 41)
        self.assertIsNone(second)

    def test_connect_false_and_exception_use_the_same_capped_backoff(self):
        self.driver.set(meters=valid_meters())

        for failure_count in range(1, 8):
            now = float(failure_count * 100)
            client = MagicMock()
            if failure_count % 2:
                client.connect.return_value = False
            else:
                client.connect.side_effect = OSError("offline")
            with patch(
                "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
                return_value=client,
            ), patch(
                "interfacers.EmonHubEcoMainInterfacer.current_time", return_value=now
            ):
                result = self.driver.read()

            self.assertIsNone(result)
            self.assertEqual(self.driver._failure_count, failure_count)
            self.assertEqual(
                self.driver._next_poll_at,
                now + min(10 * failure_count, 60),
            )
            self.driver._next_poll_at = 0.0

    def test_success_after_failure_resets_backoff_and_uses_read_interval(self):
        self.driver.set(read_interval=7.5, meters=valid_meters())
        self.driver._failure_count = 4
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_grid.return_value = grid_sample()
        reader.read_branch_device.return_value = branch_device(10.0)

        cargo, _ = self._read_with(200.0, reader)

        self.assertEqual(cargo.nodeid, 30)
        self.assertEqual(self.driver._failure_count, 0)
        self.assertEqual(self.driver._next_poll_at, 207.5)

    def test_failed_connect_backoff_starts_when_slow_attempt_completes(self):
        self.driver.set(meters=valid_meters())
        client = MagicMock()
        client.connect.return_value = False

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            return_value=client,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            side_effect=[100.0, 107.0],
        ):
            result = self.driver.read()

        self.assertIsNone(result)
        self.assertEqual(self.driver._next_poll_at, 117.0)

    def test_failed_read_backoff_starts_when_slow_attempt_completes(self):
        self.driver.set(meters=branch_meters())
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_branch_device.side_effect = [
            branch_device(10.0),
            EcoMainReadError("device 2 failed"),
        ]
        client = MagicMock()
        client.connect.return_value = True

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            return_value=client,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            side_effect=[100.0, 108.0],
        ):
            cargo = self.driver.read()

        self.assertEqual(cargo.timestamp, 100.0)
        self.assertEqual(self.driver._next_poll_at, 118.0)

    def test_success_interval_starts_when_slow_poll_completes(self):
        self.driver.set(read_interval=7.5, meters=valid_meters())
        reader = MagicMock()
        reader.read_device_info.return_value = device_info()
        reader.read_grid.return_value = grid_sample()
        reader.read_branch_device.return_value = branch_device(10.0)
        client = MagicMock()
        client.connect.return_value = True

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient",
            return_value=client,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.EcoMainReader",
            return_value=reader,
        ), patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time",
            side_effect=[100.0, 106.0],
        ):
            cargo = self.driver.read()

        self.assertEqual(cargo.timestamp, 100.0)
        self.assertEqual(self.driver._next_poll_at, 113.5)

    def test_initial_empty_meter_snapshot_never_connects_or_checks_time(self):

        with patch(
            "interfacers.EmonHubEcoMainInterfacer.ModbusTcpClient"
        ) as client_class, patch(
            "interfacers.EmonHubEcoMainInterfacer.current_time"
        ) as current_time:
            result = self.driver.read()

        self.assertIsNone(result)
        client_class.assert_not_called()
        current_time.assert_not_called()


if __name__ == "__main__":
    unittest.main()
