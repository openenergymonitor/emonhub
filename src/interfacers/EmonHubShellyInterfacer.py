"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

  Status merging and digest authentication follow aioshelly
  (https://github.com/home-assistant-libs/aioshelly, Apache License 2.0).
  Component field mapping and the zero energy counter rule follow dbus-shelly
  (https://github.com/victronenergy/dbus-shelly, MIT License,
  Copyright (c) 2022 Victron Energy BV).

"""

import base64
import copy
import hashlib
import json
import secrets
import socket
import threading
import time

import requests
import requests.auth

import Cargo
from emonhub_interfacer import EmonHubInterfacer

try:
    import websocket  # websocket-client, Debian package python3-websocket
except ImportError:
    websocket = None

"""
[[Shelly]]
    Type = EmonHubShellyInterfacer
    [[[init_settings]]]
    [[[runtimesettings]]]
        pubchannels = ToEmonCMS,
        read_interval = 10
        [[[[devices]]]]
            [[[[[heatpump]]]]]
                host = shellypro3em-aabbccddeeff.local
                fields = a_power, a_energy, a_voltage, a_current, a_pf
            [[[[[immersion]]]]]
                host = 192.168.1.20
                password = secret
                transport = http
"""

"""class EmonHubShellyInterfacer

Reads power, energy, voltage, current and switch state from Shelly Gen2 and later
devices (Pro, Plus, Gen3, Gen4) over their RPC API.

Each device in [[[[devices]]]] becomes an emoncms node of the same name. Inputs are
named <component><id>_<field>, e.g. switch0_power, light0_brightness. A component
whose type ends in a digit gets an underscore before its id: em1_0_power, pm1_0_energy.
A Pro 3EM in triphase profile gives a_power, b_energy, total_power and so on.

Device settings:
  host       IP address or hostname. Gen2+ devices answer mDNS as <device id>.local.
  fields     Input names to publish, in order. Default: every power, energy,
             voltage, current, pf, output and brightness value the device has.
             Also available: freq, ret_energy, apparent_power, temperature,
             position, n_current.
  password   Device password if authentication is enabled. Username is always admin.
  transport  ws (default) keeps one websocket open and is pushed changes;
             http polls Shelly.GetStatus every read interval. ws falls back
             to http when the websocket-client module is not installed.

Energy values are the device's lifetime counters in Wh. Log them in emoncms with
the "Wh Accumulator" process, which carries the total across a counter reset.

Every read interval, each device's latest values are published. Over a websocket
a quiet device has nothing new to say, so its last values stand while the socket
is up; a dropped socket (no ping reply within 15 s) or a failed HTTP poll
publishes nothing, so emoncms shows a gap rather than a stale value.
"""

DEFAULT_KINDS = ("power", "energy", "voltage", "current", "pf", "output", "brightness")

# switch, light, cover and pm1 components: status key -> field kind.
# A tuple key reads a nested value.
CHANNEL_KEYS = (
    ("output", "output"),
    ("brightness", "brightness"),
    ("current_pos", "position"),
    ("apower", "power"),
    ("voltage", "voltage"),
    ("current", "current"),
    ("pf", "pf"),
    ("freq", "freq"),
    (("aenergy", "total"), "energy"),
    (("ret_aenergy", "total"), "ret_energy"),
    (("temperature", "tC"), "temperature"),
)
CHANNEL_TYPES = ("switch", "light", "cover", "pm1")

# em (three phase meter) per-phase keys, without the phase prefix
EM_PHASE_KEYS = (
    ("act_power", "power"),
    ("voltage", "voltage"),
    ("current", "current"),
    ("pf", "pf"),
    ("freq", "freq"),
    ("aprt_power", "apparent_power"),
)
EM_TOTAL_KEYS = (
    ("total_act_power", "total_power", "power"),
    ("total_current", "total_current", "current"),
    ("total_aprt_power", "total_apparent_power", "apparent_power"),
    ("n_current", "n_current", "n_current"),
)
EMDATA_PHASE_KEYS = (
    ("total_act_energy", "energy"),
    ("total_act_ret_energy", "ret_energy"),
)
EMDATA_TOTAL_KEYS = (
    ("total_act", "total_energy", "energy"),
    ("total_act_ret", "total_ret_energy", "ret_energy"),
)

# em1 (single channel meter) and em1data
EM1_KEYS = (
    ("act_power", "power"),
    ("voltage", "voltage"),
    ("current", "current"),
    ("pf", "pf"),
    ("freq", "freq"),
    ("aprt_power", "apparent_power"),
)
EM1DATA_KEYS = (
    ("total_act_energy", "energy"),
    ("total_act_ret_energy", "ret_energy"),
)


def merge_status(status, params):
    """Merge NotifyStatus params into a status dict. The notification's own "ts"
    is not a component and is skipped."""
    _merge(status, {k: v for k, v in params.items() if k != "ts"})


def _merge(dest, source):
    # Deep merge, as aioshelly mergedicts()
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(dest.get(key), dict):
            _merge(dest[key], value)
        else:
            dest[key] = value


def _number(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    return None


def _lookup(status, key):
    if isinstance(key, tuple):
        for k in key:
            if not isinstance(status, dict):
                return None
            status = status.get(k)
        return status
    return status.get(key)


def _components(status):
    """Yield (type, id, prefix, component status) in the device's order."""
    for name, comp in status.items():
        ctype, _, cid = name.partition(":")
        if not cid.isdigit() or not isinstance(comp, dict):
            continue
        sep = "_" if ctype[-1].isdigit() else ""
        yield ctype, int(cid), ctype + sep + cid + "_", comp


def status_to_values(status):
    """Map a Shelly.GetStatus result to a list of (input name, kind, value).

    An energy counter reading exactly 0 is dropped together with its return
    counter: a Shelly reports 0 for a moment while booting, before restoring the
    stored total (as dbus-shelly store_energies())."""
    out = []

    def add(name, kind, value):
        value = _number(value)
        if value is not None:
            out.append((name, kind, value))

    for ctype, cid, prefix, comp in _components(status):
        if ctype in CHANNEL_TYPES:
            for key, kind in CHANNEL_KEYS:
                add(prefix + kind, kind, _lookup(comp, key))
            if _number(_lookup(comp, ("aenergy", "total"))) == 0:
                out = [v for v in out if v[0] not in (prefix + "energy", prefix + "ret_energy")]

        elif ctype in ("em", "emdata"):
            # em:0 is the common case (Pro 3EM triphase) and is left unprefixed
            prefix = "" if cid == 0 else "em%d_" % cid
            if ctype == "em":
                for phase in "abc":
                    for key, kind in EM_PHASE_KEYS:
                        add(prefix + phase + "_" + kind, kind, comp.get(phase + "_" + key))
                for key, name, kind in EM_TOTAL_KEYS:
                    add(prefix + name, kind, comp.get(key))
            else:
                for phase in "abc":
                    if _number(comp.get(phase + "_total_act_energy")) == 0:
                        continue
                    for key, kind in EMDATA_PHASE_KEYS:
                        add(prefix + phase + "_" + kind, kind, comp.get(phase + "_" + key))
                if _number(comp.get("total_act")) != 0:
                    for key, name, kind in EMDATA_TOTAL_KEYS:
                        add(prefix + name, kind, comp.get(key))

        elif ctype == "em1":
            for key, kind in EM1_KEYS:
                add(prefix + kind, kind, comp.get(key))

        elif ctype == "em1data":
            prefix = "em1_%d_" % cid
            if _number(comp.get("total_act_energy")) != 0:
                for key, kind in EM1DATA_KEYS:
                    add(prefix + kind, kind, comp.get(key))

    return out


def select_values(values, fields=None):
    """Pick (name, value) pairs to publish from status_to_values(): the named
    fields in their order, or the default kinds in device order."""
    if fields:
        lookup = {name: value for name, kind, value in values}
        return [(name, lookup[name]) for name in fields if name in lookup]
    return [(name, value) for name, kind, value in values if kind in DEFAULT_KINDS]


class DigestAuth:
    """Shelly RPC digest authentication (SHA-256), as aioshelly AuthData."""

    HA2 = hashlib.sha256(b"dummy_method:dummy_uri").hexdigest()

    def __init__(self, password, username="admin"):
        self.username = username
        self.password = password
        self.realm = None
        self.nonce = None
        self.nc = 0
        self.ha1 = None

    @staticmethod
    def _hash(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def update_challenge(self, challenge):
        if challenge.get("algorithm", "SHA-256") != "SHA-256":
            raise ValueError("Unsupported auth algorithm: %s" % challenge.get("algorithm"))
        self.realm = challenge["realm"]
        self.nonce = challenge["nonce"]
        self.nc = int(challenge.get("nc", 1))
        self.ha1 = self._hash("%s:%s:%s" % (self.username, self.realm, self.password))

    def get_auth(self):
        cnonce = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        response = self._hash("%s:%s:%s:%s:auth:%s" % (self.ha1, self.nonce, self.nc, cnonce, self.HA2))
        auth = {
            "realm": self.realm,
            "username": self.username,
            "nonce": self.nonce,
            "nc": self.nc,
            "cnonce": cnonce,
            "response": response,
            "algorithm": "SHA-256",
        }
        self.nc += 1
        return auth


class ShellyDevice:
    """One device's status cache, kept current by a background thread. The
    status is None whenever it cannot be trusted to be current."""

    def __init__(self, name, host, password=None, log=None):
        self.name = name
        self.host = host
        self.password = password
        self._log = log
        self._lock = threading.Lock()
        self._status = None
        self._status_time = None
        self._stopped = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, name="Shelly " + self.name, daemon=True)
        self._thread.start()

    def stop(self):
        self._stopped.set()

    def snapshot(self):
        """A copy of the current status and the time it was read, or (None, None)."""
        with self._lock:
            if self._status is None:
                return None, None
            return copy.deepcopy(self._status), self._status_time

    def _replace_status(self, status):
        with self._lock:
            self._status = status
            self._status_time = time.time()

    def _clear_status(self):
        with self._lock:
            self._status = None


class ShellyWsDevice(ShellyDevice):
    """Holds one websocket to ws://<host>/rpc. The device pushes NotifyStatus
    deltas on every significant change, and its meters at least once a minute;
    these are merged into the status from Shelly.GetStatus, which is re-requested
    every RESYNC_INTERVAL to pick up drift below the devices' reporting
    thresholds. A Shelly accepts a limited number of RPC connections, so a
    closed socket is never reopened before the old one is done."""

    RECONNECT_MIN = 5
    RECONNECT_MAX = 60
    RESYNC_INTERVAL = 300
    PING_INTERVAL = 10
    PING_TIMEOUT = 5

    def __init__(self, name, host, password=None, log=None):
        super().__init__(name, host, password, log)
        self.src = "emonhub-%s-%s" % (socket.gethostname(), name)
        self._ws = None
        self._connected = False
        self._next_id = 1
        self._pending = {}
        self._request_lock = threading.Lock()
        self._auth = None
        self._last_resync = 0

    def snapshot(self):
        # Pushed changes keep the status current for as long as the socket is up
        status, _ = super().snapshot()
        return status, (time.time() if status is not None else None)

    def stop(self):
        super().stop()
        ws = self._ws
        if ws is not None:
            # Don't wait for the device's close frame
            ws.close(timeout=0)

    def poll(self):
        if self._connected and time.time() - self._last_resync >= self.RESYNC_INTERVAL:
            self._last_resync = time.time()
            try:
                self._request("Shelly.GetStatus")
            except Exception as e:
                self._log.warning("Shelly %s (%s): %s", self.name, self.host, e)

    def _run(self):
        delay = self.RECONNECT_MIN
        while not self._stopped.is_set():
            self._ws = websocket.WebSocketApp(
                "ws://%s/rpc" % self.host,
                on_open=self._on_open,
                on_message=lambda ws, message: self._on_message(message),
                on_error=lambda ws, error: self._on_ws_error(error),
                on_close=lambda ws, *args: self._on_disconnected())
            started = time.time()
            try:
                self._ws.run_forever(ping_interval=self.PING_INTERVAL, ping_timeout=self.PING_TIMEOUT)
            except Exception as e:
                self._log.warning("Shelly %s (%s): %s", self.name, self.host, e)
            self._on_disconnected()
            self._ws = None
            if time.time() - started > self.RECONNECT_MAX:
                delay = self.RECONNECT_MIN
            self._stopped.wait(delay)
            delay = min(delay * 2, self.RECONNECT_MAX)

    def _on_ws_error(self, error):
        self._log.warning("Shelly %s (%s): %s", self.name, self.host, error)
        if isinstance(error, (websocket.WebSocketException, OSError)):
            # The connection is lost, e.g. no ping reply. Stop publishing now
            # rather than after websocket-client's own close timeout.
            self._on_disconnected()

    def _on_open(self, ws):
        if self._stopped.is_set():
            # stop() ran before the socket existed to close
            ws.close(timeout=0)
            return
        self._on_connected()

    def _send(self, frame):
        self._ws.send(json.dumps(frame))

    def _request(self, method, params=None, retry=False):
        with self._request_lock:
            frame = {"id": self._next_id, "src": self.src, "method": method}
            self._next_id += 1
            if params:
                frame["params"] = params
            if self._auth is not None:
                frame["auth"] = self._auth.get_auth()
            self._pending[frame["id"]] = (method, params, retry)
            # Sent under the lock so auth nc values reach the device in order
            self._send(frame)

    def _on_connected(self):
        self._log.debug("Shelly %s (%s): connected", self.name, self.host)
        self._connected = True
        self._pending = {}
        self._last_resync = time.time()
        self._request("Shelly.GetDeviceInfo")
        self._request("Shelly.GetStatus")

    def _on_disconnected(self):
        if self._connected:
            self._log.info("Shelly %s (%s): disconnected", self.name, self.host)
        self._connected = False
        self._clear_status()

    def _on_message(self, message):
        try:
            frame = json.loads(message)
        except ValueError:
            self._log.warning("Shelly %s (%s): invalid frame %s", self.name, self.host, message[:200])
            return
        self._on_frame(frame)

    def _on_frame(self, frame):
        method = frame.get("method")
        if method == "NotifyStatus":
            with self._lock:
                if self._status is not None:
                    merge_status(self._status, frame.get("params", {}))
            return
        if method == "NotifyFullStatus":
            status = dict(frame.get("params", {}))
            status.pop("ts", None)
            self._replace_status(status)
            return
        if method is not None:
            return  # NotifyEvent and others carry nothing we log

        request = self._pending.pop(frame.get("id"), None)
        if request is None:
            return
        req_method, params, retry = request

        if "error" in frame:
            self._on_error(frame["error"], req_method, params, retry)
        elif req_method == "Shelly.GetStatus":
            self._replace_status(frame.get("result", {}))
        elif req_method == "Shelly.GetDeviceInfo":
            info = frame.get("result", {})
            self._log.info("Shelly %s (%s): %s %s gen %s firmware %s", self.name, self.host,
                           info.get("id"), info.get("model"), info.get("gen"), info.get("ver"))

    def _on_error(self, error, method, params, retry):
        if error.get("code") != 401:
            self._log.warning("Shelly %s (%s): %s failed: %s", self.name, self.host, method, error)
            return
        if not self.password:
            self._log.error("Shelly %s (%s): device requires a password", self.name, self.host)
            return
        if retry:
            self._log.error("Shelly %s (%s): authentication failed, check password", self.name, self.host)
            return
        # Answer the challenge, or a stale nonce's new one, and retry once
        try:
            if self._auth is None:
                self._auth = DigestAuth(self.password)
            self._auth.update_challenge(json.loads(error.get("message", "")))
        except (ValueError, KeyError) as e:
            self._log.error("Shelly %s (%s): cannot authenticate: %s", self.name, self.host, e)
            return
        self._request(method, params, retry=True)


class ShellyHttpDevice(ShellyDevice):
    """Polls http://<host>/rpc/Shelly.GetStatus each time poll() is called."""

    TIMEOUT = 3

    def __init__(self, name, host, password=None, log=None):
        super().__init__(name, host, password, log)
        self._wake = threading.Event()
        self._auth = requests.auth.HTTPDigestAuth("admin", password) if password else None
        self._failing = False

    def stop(self):
        super().stop()
        self._wake.set()

    def poll(self):
        self._wake.set()

    def _run(self):
        self._fetch()
        while not self._stopped.is_set():
            self._wake.wait()
            self._wake.clear()
            if not self._stopped.is_set():
                self._fetch()

    def _fetch(self):
        try:
            reply = requests.get("http://%s/rpc/Shelly.GetStatus" % self.host, auth=self._auth, timeout=self.TIMEOUT)
            if reply.status_code != 200:
                raise Exception("HTTP %d" % reply.status_code)
            self._replace_status(reply.json())
        except Exception as e:
            self._clear_status()
            # Warn when polls start failing, not on every one
            log = self._log.debug if self._failing else self._log.warning
            log("Shelly %s (%s): %s", self.name, self.host, e)
            self._failing = True
            return
        if self._failing:
            self._log.info("Shelly %s (%s): reachable again", self.name, self.host)
            self._failing = False


def make_device(name, config, log):
    """Create the device for one [[[[devices]]]] entry, without starting it."""
    transport = config.get("transport", "ws")
    if transport == "ws" and websocket is None:
        log.warning("Shelly %s: websocket-client not installed, polling over HTTP instead", name)
        transport = "http"
    cls = ShellyWsDevice if transport == "ws" else ShellyHttpDevice
    return cls(name, config["host"], password=config.get("password"), log=log)


class EmonHubShellyInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        super().__init__(name)
        self._shelly_settings = {'read_interval': 10.0, 'devices': {}}
        self._settings['read_interval'] = 10.0
        self._devices = {}
        self._device_config = {}
        self._next_read = 0
        self._queue = []
        self._missing_fields = set()
        # Guards _devices against set() from the main thread, and stops set()
        # starting devices once run() has ended
        self._devices_lock = threading.Lock()
        self._closed = False

    def run(self):
        try:
            super().run()
        finally:
            self._stop_devices()

    def _stop_devices(self):
        with self._devices_lock:
            self._closed = True
            for device in self._devices.values():
                device.stop()
            self._devices = {}
            self._device_config = {}

    def read(self):
        """Every read_interval, sample each device's status and queue a cargo per
        device; return them one per call."""
        now = time.time()
        if now >= self._next_read:
            interval = self._settings['read_interval']
            self._next_read = (now // interval + 1) * interval
            for name, device in list(self._devices.items()):
                # Over HTTP this is the previous poll's status, stamped with its time
                status, timestamp = device.snapshot()
                device.poll()
                if status is None:
                    continue
                fields = self._device_config.get(name, {}).get("fields")
                values = select_values(status_to_values(status), fields)
                self._warn_missing(name, fields, values)
                if not values:
                    continue
                c = Cargo.new_cargo(timestamp=timestamp)
                c.nodeid = name
                c.names = [n for n, v in values]
                c.realdata = [v for n, v in values]
                self._queue.append(c)

        if self._queue:
            return self._queue.pop(0)
        return False

    def _warn_missing(self, name, fields, values):
        """Warn once for each configured field the device does not report."""
        found = {n for n, v in values}
        for field in fields or ():
            if field not in found and (name, field) not in self._missing_fields:
                self._missing_fields.add((name, field))
                self._log.warning("Shelly %s: device has no field %s", name, field)

    def set(self, **kwargs):
        for key, setting in self._shelly_settings.items():
            if key in kwargs:
                setting = kwargs[key]
            if key == 'read_interval':
                setting = float(setting)
                if setting < 1:
                    self._log.warning("Shelly %s: read_interval must be at least 1, using 1", self.name)
                    setting = 1.0
                if self._settings.get(key) != setting:
                    self._log.info("Setting %s read_interval: %s", self.name, setting)
                    self._settings[key] = setting
            elif key == 'devices':
                self._set_devices(setting)

        # include kwargs from parent
        super().set(**kwargs)

    def _set_devices(self, devices):
        wanted = {}
        for name, conf in devices.items():
            if 'host' not in conf:
                self._log.warning("Shelly %s: no host set", name)
                continue
            config = {'host': str(conf['host'])}
            if 'fields' in conf:
                fields = conf['fields']
                if isinstance(fields, str):
                    fields = [f.strip() for f in fields.split(",")]
                config['fields'] = [str(f) for f in fields if f]
            for key in ('password', 'transport'):
                if key in conf:
                    config[key] = str(conf[key])
            if config.get('transport', 'ws') not in ('ws', 'http'):
                self._log.warning("Shelly %s: unknown transport %s", name, config['transport'])
                continue
            wanted[name] = config

        with self._devices_lock:
            if not self._closed:
                self._update_devices(wanted)

    def _update_devices(self, wanted):
        for name in list(self._devices):
            if self._device_config.get(name) != wanted.get(name):
                self._log.info("Shelly %s: removed", name)
                self._devices.pop(name).stop()
                del self._device_config[name]
                self._missing_fields = {m for m in self._missing_fields if m[0] != name}

        for name, config in wanted.items():
            if name in self._devices:
                continue
            self._log.info("Shelly %s: %s", name, config['host'])
            device = make_device(name, config, self._log)
            device.start()
            self._devices[name] = device
            self._device_config[name] = config
