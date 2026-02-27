#!/usr/bin/python3
# EmonHubEconextInterfacer released for use by OpenEnergyMonitor project

__author__ = "Linus Reitmayr"

import sys
import time
import traceback

import Cargo
import requests
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubEconextInterfacer

Fetch metrics from econext-gateway (RS-485 gateway for GM3 based heat pump controllers)

"""


class EmonHubEconextInterfacer(EmonHubInterfacer):

    # Default parameter mappings: (gateway_name, emoncms_name)
    # Config entries with matching gateway_name override the emoncms_name.
    # DHWStatus and CHStatus are computed from flapValveStates and always included.
    DEFAULT_PARAMETERS = [
        ("TempWthr", "OutdoorTemp"),
        ("Circuit2CalcTemp", "Circuit2TargetTemp"),
        ("HDWTSetPoint", "DHWSetPoint"),
        ("TempCWU", "DHWTemp"),
        ("Circuit2thermostatTemp", "RoomTemp"),
        ("HeatSourceCalcPresetTemp", "TargetTemp"),
        ("currentFlow", "FlowRate"),
        ("HPStatusFanRPM", "FanSpeed"),
        ("HPStatusComprHz", "CompressorFreq"),
    ]

    def __init__(self, name, host="", port=8000, pollinterval=60, nodeid=30):
        """Initialize interfacer

        Args:
            name (str): Interfacer name
            host (str): Gateway host/IP address
            port (int): Gateway port (default 8000)
            pollinterval (int): Polling interval in seconds
            nodeid (int): Node ID for data
        """

        # Initialization
        super().__init__(name)

        # Interfacer specific settings with defaults
        self._template_settings = {
            "host": host,
            "port": port,
            "pollinterval": int(pollinterval),
            "nodeid": int(nodeid),
            "nodename": name,
            "timeout": 10,
        }

        # Initialize settings from template
        for key, val in self._template_settings.items():
            self._settings[key] = val

        self._next_poll_time = None
        self._consecutive_failures = 0

        # User-configured parameter overrides/additions: list of (gateway_name, emoncms_name)
        self._config_parameters = []

    def close(self):
        """Close interfacer"""
        pass

    def _set_poll_timer(self, seconds):
        """Set next poll time

        Args:
            seconds (int): Seconds until next poll
        """
        self._next_poll_time = time.time() + seconds

    def _is_it_time(self):
        """Check if it's time to poll

        Returns:
            bool: True if ready to poll
        """
        if not self._next_poll_time:  # First time loop
            return True

        return time.time() > self._next_poll_time

    def _parse_parameters(self, raw):
        """Parse parameters config value.

        Args:
            raw: String or list from configobj. Each entry is either:
                 "GatewayName" (passed through using the gateway name) or
                 "GatewayName:FeedName" (gateway param mapped to custom feed name)

        Returns:
            list of (gateway_name, feed_name) tuples
        """
        if isinstance(raw, str):
            entries = [raw]
        elif isinstance(raw, (list, tuple)):
            entries = list(raw)
        else:
            self._log.warning("Invalid parameters format: %s", raw)
            return []

        result = []
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            if ":" in entry:
                gateway_name, feed_name = entry.split(":", 1)
                gateway_name = gateway_name.strip()
                feed_name = feed_name.strip()
                if not gateway_name or not feed_name:
                    self._log.warning("Invalid parameters entry: '%s'", entry)
                    continue
            else:
                gateway_name = entry
                feed_name = entry

            result.append((gateway_name, feed_name))

        return result

    # Override base _process_rx code from emonhub_interfacer
    def _process_rx(self, rxc):
        if not rxc:
            return False

        return rxc

    # Override base read code from emonhub_interfacer
    def read(self):
        """Read data from gateway

        Returns:
            Cargo object with data, or None if not ready/error
        """

        # Wait until we are ready to fetch
        if not self._is_it_time():
            return None

        # Validate required settings
        if not self._settings.get("host"):
            self._log.error("Host not configured")
            self._set_poll_timer(60)
            return None

        cargo = None

        try:
            cargo = self._fetch()

            # Poll timer reset after successful fetch
            self._set_poll_timer(self._settings["pollinterval"])
            self._consecutive_failures = 0

        except requests.exceptions.Timeout as err:
            self._log.warning("Request timeout connecting to %s: %s", self._settings["host"], err)
            self._consecutive_failures += 1
            retry_interval = min(60, 10 * self._consecutive_failures)  # Backoff: 10s, 20s, 30s... max 60s
            self._log.info("Retrying in %d seconds", retry_interval)
            self._set_poll_timer(retry_interval)

        except requests.exceptions.ConnectionError as err:
            self._log.warning("Connection error to %s: %s", self._settings["host"], err)
            self._consecutive_failures += 1
            retry_interval = min(60, 10 * self._consecutive_failures)
            self._log.info("Retrying in %d seconds", retry_interval)
            self._set_poll_timer(retry_interval)

        except requests.exceptions.RequestException as err:
            self._log.error("HTTP request failed: %s", err)
            self._consecutive_failures += 1
            retry_interval = min(60, 10 * self._consecutive_failures)
            self._set_poll_timer(retry_interval)

        except Exception as err:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self._log.error("Unexpected error: %s", err)
            self._log.debug(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            self._consecutive_failures += 1
            retry_interval = min(60, 10 * self._consecutive_failures)
            self._set_poll_timer(retry_interval)

        return cargo

    def _fetch(self):
        """Fetch data from gateway

        Returns:
            Cargo object with fetched data

        Raises:
            requests.exceptions.RequestException: On HTTP errors
            Exception: On data parsing errors
        """
        timeout = self._settings.get("timeout", 10)
        host = self._settings["host"]
        port = self._settings["port"]

        url = f"http://{host}:{port}/api/parameters"
        self._log.debug("Fetching from %s", url)

        r = requests.get(url, timeout=timeout)
        r.raise_for_status()

        # Gateway returns: {"parameters": {"<index>": {"index": N, "name": "...", "value": V, ...}}}
        # Build name->value lookup from index-keyed response
        data = {}
        try:
            raw_params = r.json()["parameters"]
            params = {p["name"]: p["value"] for p in raw_params.values()}

            # Computed parameters (always included, need special transforms)
            data["DHWStatus"] = int(params["flapValveStates"]) == 3
            data["CHStatus"] = int(params["flapValveStates"]) == 0

        except (ValueError, KeyError) as e:
            raise Exception("Invalid data from gateway") from e

        # Build effective mapping: defaults overridden/extended by config
        config_by_gw = dict(self._config_parameters)
        mapping = [(gw, config_by_gw.pop(gw, feed)) for gw, feed in self.DEFAULT_PARAMETERS]
        mapping.extend(config_by_gw.items())  # remaining config entries are additions

        for gateway_name, feed_name in mapping:
            if gateway_name in params:
                data[feed_name] = params[gateway_name]
            else:
                self._log.warning(
                    "Parameter '%s' not found in gateway response", gateway_name
                )

        self._log.debug("Fetched data: %s", data)

        # Cargo object for returning values
        c = Cargo.new_cargo()
        c.rawdata = None
        c.realdata = list(data.values())
        c.names = list(data.keys())
        c.nodeid = self._settings["nodeid"]
        c.nodename = self._settings["nodename"]

        return c

    def set(self, **kwargs):
        """Set interfacer settings

        Args:
            **kwargs: Settings to update
        """
        # Handle parameters separately (needs custom parsing)
        if "parameters" in kwargs:
            parsed = self._parse_parameters(kwargs["parameters"])
            if parsed != self._config_parameters:
                self._config_parameters = parsed
                self._log.info(
                    "Setting %s parameters: %s",
                    self.name,
                    ", ".join(
                        f"{gw}->{feed}" if gw != feed else gw
                        for gw, feed in parsed
                    ),
                )

        for key, setting in self._template_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._template_settings[key]

            # Skip if unchanged
            if key in self._settings and self._settings[key] == setting:
                continue

            # Handle specific settings
            if key in ["pollinterval", "nodeid", "timeout"]:
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = int(setting)
            elif key in ["host", "port", "nodename"]:
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = str(setting)
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # Include kwargs from parent
        super().set(**kwargs)
