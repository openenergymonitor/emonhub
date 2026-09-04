from collections import deque
from collections.abc import Mapping
import math
import re
import time

import Cargo
from emonhub_interfacer import EmonHubInterfacer

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    try:
        from pymodbus.client.sync import ModbusTcpClient
    except ImportError:
        ModbusTcpClient = None

from ecomain.protocol import EcoMainReadError, EcoMainReader


current_time = time.time


SINGLE_PHASE_NAMES = (
    "power",
    "energy",
    "return_energy",
    "voltage",
    "current",
    "power_factor",
)

THREE_PHASE_NAMES = (
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
)

ECOMAIN_PORT = 502
ECOMAIN_UNIT_ID = 255
EXPECTED_MODEL = "2401"
MINIMUM_SOFTWARE_VERSION = 139


class EcoMainConfigError(ValueError):
    pass


def _apply_invert(sample, invert):
    result = dict(sample)
    if invert:
        result["power"] = -result["power"]
        result["power_factor"] = -result["power_factor"]
        result["energy"], result["return_energy"] = (
            result["return_energy"],
            result["energy"],
        )
    return result


def _build_single_phase_cargo(meter, sample, timestamp):
    values = [sample[name] for name in SINGLE_PHASE_NAMES]
    return Cargo.new_cargo(
        nodeid=meter["nodeid"],
        nodename=meter["nodename"],
        names=list(SINGLE_PHASE_NAMES),
        realdata=values,
        timestamp=timestamp,
    )


def _build_three_phase_cargo(meter, phases, timestamp, totals=None):
    if len(phases) != 3:
        raise EcoMainConfigError(
            "three-phase cargo requires exactly three phases"
        )

    if totals is None:
        totals = {
            name: sum(phase[name] for phase in phases)
            for name in ("power", "energy", "return_energy")
        }

    values = [
        totals["power"],
        totals["energy"],
        totals["return_energy"],
    ]
    for name in ("power", "voltage", "current", "power_factor"):
        values.extend(phase[name] for phase in phases)

    return Cargo.new_cargo(
        nodeid=meter["nodeid"],
        nodename=meter["nodename"],
        names=list(THREE_PHASE_NAMES),
        realdata=values,
        timestamp=timestamp,
    )


def _parse_phase(value):
    parts = str(value).split(":")
    if len(parts) != 3:
        raise EcoMainConfigError(
            "phase must use device:channel:invert format"
        )

    try:
        device = int(parts[0])
        channel = int(parts[1])
    except (TypeError, ValueError) as exc:
        raise EcoMainConfigError(
            "phase device and channel must be integers"
        ) from exc

    invert_text = parts[2].lower()
    if invert_text not in ("true", "false"):
        raise EcoMainConfigError("phase invert must be true or false")
    if device not in range(4):
        raise EcoMainConfigError("phase device must be 0..3")
    if channel not in range(1, 11):
        raise EcoMainConfigError("phase channel must be 1..10")

    return {
        "device": device,
        "channel": channel,
        "invert": invert_text == "true",
    }


def _parse_meters(meters):
    try:
        entries = meters.items()
    except AttributeError as exc:
        raise EcoMainConfigError("meters must be a mapping") from exc

    parsed = []
    nodeids = set()
    nodenames = set()
    branches = set()
    grid_count = 0

    for meter_name, config in entries:
        try:
            nodeid = int(config.get("nodeid"))
        except (AttributeError, TypeError, ValueError) as exc:
            raise EcoMainConfigError(
                f"meter {meter_name} nodeid must be an integer"
            ) from exc
        if nodeid in nodeids:
            raise EcoMainConfigError(f"duplicate nodeid {nodeid}")

        try:
            raw_nodename = config.get("nodename")
        except AttributeError as exc:
            raise EcoMainConfigError(
                f"meter {meter_name} must be a mapping"
            ) from exc
        nodename = "" if raw_nodename is None else str(raw_nodename).strip()
        if not nodename:
            raise EcoMainConfigError(f"meter {meter_name} nodename must not be empty")
        if re.fullmatch(r"[\w .-]+", nodename) is None:
            raise EcoMainConfigError(
                f"meter {meter_name} nodename contains unsupported characters"
            )
        if nodename in nodenames:
            raise EcoMainConfigError(f"duplicate nodename {nodename}")

        source = str(config.get("source", "")).strip()
        if source not in ("grid", "branches"):
            raise EcoMainConfigError(
                f"meter {meter_name} source must be grid or branches"
            )

        if source == "grid":
            if "phases" in config:
                raise EcoMainConfigError(
                    f"grid meter {meter_name} must not define phases"
                )
            grid_count += 1
            if grid_count > 1:
                raise EcoMainConfigError("only one grid meter is allowed")
            phases = ()
        else:
            if "phases" not in config:
                raise EcoMainConfigError(
                    f"branch meter {meter_name} must define phases"
                )
            raw_phases = config["phases"]
            if isinstance(raw_phases, Mapping):
                raise EcoMainConfigError(
                    f"branch meter {meter_name} phases must be a string or list"
                )
            if isinstance(raw_phases, str):
                raw_phases = [raw_phases]
            try:
                phase_count = len(raw_phases)
            except TypeError as exc:
                raise EcoMainConfigError(
                    f"branch meter {meter_name} phases must be a list"
                ) from exc
            if phase_count not in (1, 3):
                raise EcoMainConfigError(
                    f"branch meter {meter_name} must define one or three phases"
                )

            parsed_phases = []
            for raw_phase in raw_phases:
                phase = _parse_phase(raw_phase)
                branch = (phase["device"], phase["channel"])
                if branch in branches:
                    raise EcoMainConfigError(
                        f"branch {branch[0]}:{branch[1]} is used more than once"
                    )
                branches.add(branch)
                parsed_phases.append(phase)
            phases = tuple(parsed_phases)

        nodeids.add(nodeid)
        nodenames.add(nodename)
        parsed.append(
            {
                "name": str(meter_name),
                "nodeid": nodeid,
                "nodename": nodename,
                "source": source,
                "phases": phases,
            }
        )

    if not parsed:
        raise EcoMainConfigError("at least one meter must be configured")
    return tuple(parsed)


def _parse_read_interval(value):
    try:
        interval = float(value)
    except (TypeError, ValueError) as exc:
        raise EcoMainConfigError(
            "read_interval must be a finite number greater than zero"
        ) from exc
    if not math.isfinite(interval) or interval <= 0:
        raise EcoMainConfigError(
            "read_interval must be a finite number greater than zero"
        )
    return interval


def _parse_connection_settings(host, serial, timeout):
    parsed_host = "" if host is None else str(host).strip()
    if not parsed_host:
        raise EcoMainConfigError("host must not be empty")

    parsed_serial = "" if serial is None else str(serial).strip()
    if re.fullmatch(r"[0-9]{12}", parsed_serial) is None:
        raise EcoMainConfigError("serial must contain exactly 12 digits")

    try:
        parsed_timeout = float(str(timeout).strip())
    except (AttributeError, TypeError, ValueError) as exc:
        raise EcoMainConfigError(
            "timeout must be a finite number greater than zero"
        ) from exc
    if not math.isfinite(parsed_timeout) or parsed_timeout <= 0:
        raise EcoMainConfigError(
            "timeout must be a finite number greater than zero"
        )

    return {
        "host": parsed_host,
        "serial": parsed_serial,
        "timeout": parsed_timeout,
    }


def _validate_device_info(info, expected_serial):
    if not isinstance(info, Mapping):
        raise EcoMainReadError("device info unavailable")

    model = info.get("model")
    if model != EXPECTED_MODEL:
        raise EcoMainReadError(f"unexpected model {model!r}")

    versions = info.get("versions")
    software = (
        versions.get("ecomain_software")
        if isinstance(versions, Mapping)
        else None
    )
    if isinstance(software, bool) or not isinstance(software, int):
        raise EcoMainReadError("unsupported software version: unavailable")
    if software < MINIMUM_SOFTWARE_VERSION:
        raise EcoMainReadError(f"unsupported software version {software}")

    serial = info.get("serial")
    if serial != expected_serial:
        raise EcoMainReadError("serial number mismatch")


class EmonHubEcoMainInterfacer(EmonHubInterfacer):
    def __init__(self, name, host="", serial="", timeout=3):
        super().__init__(name)
        self.init_settings = {
            "host": host,
            "serial": serial,
            "timeout": timeout,
        }
        self._connection_settings = None
        try:
            connection_settings = _parse_connection_settings(
                host, serial, timeout
            )
        except EcoMainConfigError as exc:
            self._log.warning(
                "Invalid %s connection configuration: %s", name, exc
            )
        else:
            self.init_settings = dict(connection_settings)
            self._connection_settings = connection_settings
        self._settings["read_interval"] = 10.0
        self._meters = ()
        self._pending = deque()
        self._client = None
        self._reader = None
        self._next_poll_at = 0.0
        self._failure_count = 0

    def set(self, **kwargs):
        try:
            read_interval = self._settings["read_interval"]
            if "read_interval" in kwargs:
                read_interval = _parse_read_interval(kwargs["read_interval"])

            meters = self._meters
            if "meters" in kwargs:
                meters = _parse_meters(kwargs["meters"])
        except EcoMainConfigError as exc:
            self._log.warning("Invalid %s configuration: %s", self.name, exc)
            return

        parent_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in ("read_interval", "meters")
        }
        super().set(**parent_kwargs)
        self._settings["read_interval"] = read_interval
        self._meters = meters
        if "meters" in kwargs:
            self._pending.clear()

    def _process_rx(self, cargo):
        # Meter-local names are authoritative over global [nodes] mappings.
        logical_nodename = cargo.nodename
        processed = super()._process_rx(cargo)
        if processed and logical_nodename:
            processed.nodename = logical_nodename
        return processed

    def _connect(self):
        settings = self._connection_settings
        if settings is None:
            return False
        if ModbusTcpClient is None:
            self._log.warning(
                "Failed to connect %s: pymodbus is not installed",
                self.name,
            )
            return False
        try:
            client = ModbusTcpClient(
                host=settings["host"],
                port=ECOMAIN_PORT,
                timeout=settings["timeout"],
            )
            self._client = client
            if not client.connect():
                self._log.warning(
                    "Failed to connect %s to %s:%s",
                    self.name,
                    settings["host"],
                    ECOMAIN_PORT,
                )
                self._disconnect()
                return False

            self._reader = EcoMainReader(
                client,
                unit_id=ECOMAIN_UNIT_ID,
            )
        except Exception as exc:
            self._log.warning("Failed to connect %s: %s", self.name, exc)
            self._disconnect()
            return False

        try:
            info = self._reader.read_device_info()
            _validate_device_info(info, settings["serial"])
        except Exception as exc:
            self._log.warning(
                "Connected %s but device identity validation failed: %s",
                self.name,
                exc,
            )
            self._disconnect()
            return False
        self._log.info("Connected %s device: %s", self.name, info)
        return True

    def _disconnect(self):
        client = self._client
        self._reader = None
        self._client = None
        if client is None:
            return
        try:
            client.close()
        except Exception as exc:
            self._log.warning("Failed to close %s connection: %s", self.name, exc)

    def _set_next_poll(self, now, succeeded):
        if succeeded:
            self._failure_count = 0
            delay = self._settings["read_interval"]
        else:
            self._failure_count += 1
            delay = min(10 * self._failure_count, 60)
        self._next_poll_at = now + delay

    def _poll(self, timestamp):
        requirements = []
        seen = set()
        for meter in self._meters:
            if meter["source"] == "grid":
                requirement = ("grid", None)
            else:
                for phase in meter["phases"]:
                    requirement = ("branches", phase["device"])
                    if requirement not in seen:
                        seen.add(requirement)
                        requirements.append(requirement)
                continue
            if requirement not in seen:
                seen.add(requirement)
                requirements.append(requirement)

        grid = None
        branches = {}
        succeeded = True
        try:
            for source, device in requirements:
                if source == "grid":
                    grid = self._reader.read_grid()
                else:
                    branches[device] = self._reader.read_branch_device(device)
        except EcoMainReadError as exc:
            succeeded = False
            self._log.warning("Failed to poll %s: %s", self.name, exc)

        cargos = []
        for meter in self._meters:
            if meter["source"] == "grid":
                if grid is None:
                    continue
                cargos.append(
                    _build_three_phase_cargo(
                        meter,
                        grid["phases"],
                        timestamp,
                        totals=grid,
                    )
                )
                continue

            if any(phase["device"] not in branches for phase in meter["phases"]):
                continue
            phases = [
                _apply_invert(
                    branches[phase["device"]][phase["channel"]],
                    phase["invert"],
                )
                for phase in meter["phases"]
            ]
            if len(phases) == 1:
                cargos.append(_build_single_phase_cargo(meter, phases[0], timestamp))
            else:
                cargos.append(_build_three_phase_cargo(meter, phases, timestamp))
        return cargos, succeeded

    def read(self):
        if self._pending:
            return self._pending.popleft()
        if not self._meters or self._connection_settings is None:
            return None

        now = current_time()
        if now < self._next_poll_at:
            return None

        if self._reader is None and not self._connect():
            self._set_next_poll(current_time(), False)
            return None

        cargos, succeeded = self._poll(now)
        if not succeeded:
            self._disconnect()
        self._set_next_poll(current_time(), succeeded)
        self._pending.extend(cargos)
        if self._pending:
            return self._pending.popleft()
        return None

    def close(self):
        self._disconnect()
