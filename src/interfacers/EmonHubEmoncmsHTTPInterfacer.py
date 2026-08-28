"""class EmonHubEmoncmsHTTPInterfacer
"""
import time
import json
import math
import random
import requests
import zlib
from binascii import hexlify
from emonhub_interfacer import EmonHubInterfacer
import emonhub_version

class EmonHubEmoncmsHTTPInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        # Initialization
        super().__init__(name)

        # add or alter any default settings for this reporter
        # defaults previously defined in inherited emonhub_interfacer
        # here we are just changing the batchsize from 1 to 100
        # and the interval from 0 to 30
        self._defaults.update({'batchsize': 1000, 'interval': 30})
        # This line will stop the default values printing to logfile at start-up
        self._settings.update(self._defaults)

        # interfacer specific settings
        self._cms_settings = {
            'apikey': "",
            'url': "http://emoncms.org",
            'senddata': 1,
            'sendstatus': 0,
            'sendnames': 0,
            'compress': 0
        }

        # set an absolute upper limit for number of items to process per post
        self._item_limit = 1000

        # maximum buffer size
        self.buffer._maximumEntriesInBuffer = 100000

        # Retry backoff state, see _schedule_retry
        self._retry_not_before = 0
        self._consecutive_failures = 0
        # Longest a failing post will wait before trying again. Raised in
        # _schedule_retry for a long posting interval, since a cap at or below
        # the interval can never take effect.
        self._retry_backoff_max = 300

        self.session = requests.Session()
        # Identify ourselves so that server operators can tell emonhub traffic
        # apart from everything else, and see the version distribution of the
        # fleet. The requests default is appended rather than replaced so that
        # the previous 'python-requests/x.y.z' signature still matches.
        self.session.headers.update({
            'User-Agent': 'emonhub/%s %s' % (
                emonhub_version.version, requests.utils.default_user_agent())
        })

    def add(self, cargo):
        """Append data to buffer.

        """
        
        f = []
        try:
            f.append(int(cargo.timestamp))
            
            if cargo.nodename and self._settings['sendnames']:
                f.append(cargo.nodename)
            else:
                f.append(cargo.nodeid)
            
            if len(cargo.names) == len(cargo.realdata) and self._settings['sendnames']:
                keyvalues = {}
                for name, value in zip(cargo.names, cargo.realdata):
                    keyvalues[name] = value
                if cargo.rssi:
                    keyvalues['rssi'] = cargo.rssi
                f.append(keyvalues)
            else:
                for i in cargo.realdata:
                    f.append(i)
                if cargo.rssi:
                    f.append(cargo.rssi)
                # Note if number of names and values do not match
                if len(cargo.names) > 0 and self._settings['sendnames']:
                    self._log.warning("cargo.names and cargo.realdata have different lengths - " + str(len(cargo.names)) + " vs " + str(len(cargo.realdata)))
        except:
            # Only buffer a frame that was built without error. A frame that
            # failed partway is incomplete, and an empty one causes emoncms to
            # reject the whole batch it is sent in.
            self._log.warning("Failed to create emonCMS frame %s", f)
        else:
            self.buffer.storeItem(f)

    def _is_encodable(self, value):
        """Check a single value can be sent to emoncms as valid JSON.

        A NaN or Inf from a misbehaving node is the usual cause of a value
        failing here.
        """

        if isinstance(value, float) and not math.isfinite(value):
            return False
        try:
            json.dumps(value, allow_nan=False)
        except (ValueError, TypeError):
            return False
        return True

    def _sanitise_frame(self, frame):
        """Replace the values in a frame that cannot be encoded as JSON.

        Frames are [timestamp, nodeid, value, ...] or, with sendnames enabled,
        [timestamp, nodename, {name: value, ...}].

        A positional value is replaced with None rather than removed, so that
        the index of every value after it is unchanged: emoncms names the
        inputs in a bulk frame by position, and skips a null instead of
        storing it, so [100, null, 200] still arrives as input 1 = 100 and
        input 3 = 200. A named value is dropped from the dict instead, as
        there is no index to preserve and emoncms casts a null in the
        key/value form to 0.

        Returns (frame, values dropped), or (None, 0) if the frame as a whole
        cannot be used.
        """

        # A frame needs a timestamp, a node id and at least one value; emoncms
        # ignores anything shorter. Neither of the first two fields can be
        # replaced with a null without changing what the frame means, so give
        # up on the whole frame if either of them is unusable.
        if len(frame) < 3 or not all(self._is_encodable(v) for v in frame[:2]):
            return None, 0

        sanitised = list(frame[:2])
        dropped = 0

        for value in frame[2:]:
            if isinstance(value, dict):
                keep = {k: v for k, v in value.items() if self._is_encodable(v)}
                dropped += len(value) - len(keep)
                sanitised.append(keep)
            elif self._is_encodable(value):
                sanitised.append(value)
            else:
                sanitised.append(None)
                dropped += 1

        return sanitised, dropped

    def _process_reply(self, reply, dt, number_of_frames):
        """Decide what to do with the batch just posted, from the server's reply.

        Returns True to discard the batch and False to keep it for a retry.

        The distinction that matters is between data emoncms will never accept
        and a problem that will clear on its own or once someone fixes it. The
        first has to be discarded: retrying it forever blocks the head of the
        buffer, so nothing behind it gets through either and the backlog grows
        until the oldest data is dropped. The second has to be kept, since that
        is the whole point of buffering.

        Anything unrecognised keeps the data. The buffer exists to ride out
        problems we did not anticipate, so retrying is the safe default.
        """

        body = reply.text.strip() if reply.text else ''

        if reply.status_code == 200 and body == 'ok':
            self._log.debug("acknowledged receipt with 'ok' from %s (%d ms)",
                            self._settings['url'], dt)
            self._retry_succeeded()
            return True

        # Data emoncms will never accept, so discard it rather than block the
        # buffer behind it. Current emoncms reports this as 400; older versions
        # reply 200 with the message in the body, bare on emoncms.org and
        # wrapped in JSON when self hosted, hence matching on the text too.
        if reply.status_code == 400 or (reply.status_code == 200 and 'Format error' in body):
            self._log.warning("%s discarding %d frame(s) rejected as invalid by %s: %s",
                              self.name, number_of_frames, self._settings['url'], body[:200])
            # A rejection still means emoncms answered us, so the link is fine.
            self._retry_succeeded()
            return True

        # Problems someone can fix, where the data itself is fine. Keep it so it
        # goes through once the cause is put right, but say so plainly: without
        # this the buffer just fills and starts discarding the oldest data with
        # nothing in the log to explain why.
        if reply.status_code in (401, 403):
            self._log.warning("%s not authorised by %s, check apikey. Data is being "
                              "kept and will be sent once this is fixed",
                              self.name, self._settings['url'])
            self._schedule_retry()
            return False

        if reply.status_code == 413:
            self._log.warning("%s batch of %d frames rejected as too large by %s, "
                              "reduce batchsize. Data is being kept",
                              self.name, number_of_frames, self._settings['url'])
            self._schedule_retry()
            return False

        if reply.status_code == 429:
            # Wait as asked before posting again, rather than spending the
            # backlog retrying into a server that is telling us to slow down.
            delay = self._retry_after_seconds(reply)
            self._retry_not_before = time.time() + delay
            self._log.warning("%s rate limited by %s, not retrying for %d seconds. "
                              "Data is being kept",
                              self.name, self._settings['url'], delay)
            # _schedule_retry never shortens a wait, so the Retry-After value
            # stands unless repeated failures warrant an even longer pause.
            self._schedule_retry()
            return False

        if reply.status_code >= 500:
            self._log.warning("%s server error %d from %s, data is being kept",
                              self.name, reply.status_code, self._settings['url'])
            self._schedule_retry()
            return False

        # Anything else, including a 200 whose body is not 'ok', which is far
        # more likely to be a captive portal or proxy page than emoncms.
        self._log.warning("%s unexpected reply from %s (HTTP %d), data is being kept: %s",
                          self.name, self._settings['url'], reply.status_code, body[:200])
        self._schedule_retry()
        return False

    def _schedule_retry(self):
        """Wait longer before trying again, the longer the server has been failing.

        The first failure retries at the normal interval, since a single blip is
        not worth slowing down for. After that the wait doubles, up to
        _retry_backoff_max, so a long outage is not spent posting into a server
        that is not there.

        The wait is jittered because every hub posting to the same server would
        otherwise back off in step and come back all at once the moment it
        recovers, which is when it can least afford the traffic. Never shortens
        a wait already set, so an explicit Retry-After still stands.
        """

        self._consecutive_failures += 1
        if self._consecutive_failures < 2:
            return

        interval = max(int(self._settings['interval']), 1)
        # The wait is only tested when the next attempt comes round, so a cap at
        # or below the posting interval would always have expired by then and
        # the backoff would do nothing. Keep the cap above the interval, with an
        # absolute ceiling so recovery is never delayed by more than an hour.
        # At the default 30s interval this is the plain 300s cap.
        cap = min(max(self._retry_backoff_max, interval * 4), 3600)
        # Cap the exponent as well as the delay, so a long outage cannot build
        # an absurdly large number before the cap is applied.
        delay = min(interval * 2 ** min(self._consecutive_failures - 1, 16), cap)
        delay *= random.uniform(0.5, 1.0)
        self._retry_not_before = max(self._retry_not_before, time.time() + delay)
        self._log.debug("%s waiting %d seconds before retrying, %d attempts have failed",
                        self.name, delay, self._consecutive_failures)

    def _retry_succeeded(self):
        """Clear the backoff after the server answers properly again."""

        if self._consecutive_failures >= 2:
            self._log.info("%s posting to %s resumed after %d failed attempts",
                           self.name, self._settings['url'], self._consecutive_failures)
        self._consecutive_failures = 0
        self._retry_not_before = 0

    def _retry_after_seconds(self, reply):
        """Seconds to wait from a Retry-After header, clamped to something sane."""

        header = reply.headers.get('Retry-After', '') if reply.headers else ''
        try:
            delay = int(float(header.strip()))
        except (AttributeError, ValueError):
            # Absent, or an HTTP date rather than a number, which is rare enough
            # not to be worth parsing. Fall back to a sensible pause.
            delay = 300
        # Never wait less than the posting interval, and never so long that a
        # bad header effectively stops the interfacer.
        return max(int(self._settings['interval']), min(delay, 3600))

    def _process_post(self, databuffer):
        """Send data to server."""

        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 250 ...]]

        if 'apikey' not in self._settings or len(str(self._settings['apikey'])) != 32 \
                or str(self._settings['apikey']).lower() == 'x' * 32:
            # Return true to clear buffer if the apikey is not set
            return True

        # The server asked us to back off. Keep the data and say nothing until
        # the wait is up, rather than posting into a server we know will refuse.
        if time.time() < self._retry_not_before:
            return False

        if self._settings['senddata']:
            number_of_frames = len(databuffer)
            
            # Set allow_nan=False as the NaN literal json produces by default is
            # not valid JSON and would be rejected by emoncms, blocking the head
            # of the buffer so that no data gets through at all.
            #
            # Encoding failures must not be allowed to escape this method. They
            # would propagate up through flush() and action() to run(), killing
            # the interfacer thread; emonhub then rebuilds a dead interfacer from
            # its settings, which silently discards the whole buffered backlog -
            # exactly the data we are trying to protect during an outage.
            # Instead, null out just the offending values and send the rest.
            try:
                data_string = json.dumps(databuffer, separators=(',', ':'), allow_nan=False)
            except (ValueError, TypeError) as ex:
                sanitised = []
                dropped_values = 0
                dropped_frames = 0
                affected = set()
                for frame in databuffer:
                    clean, dropped = self._sanitise_frame(frame)
                    dropped_values += dropped
                    if clean is None:
                        dropped_frames += 1
                    else:
                        sanitised.append(clean)
                    if dropped or clean is None:
                        # frame[1] is the node id, absent from a truncated frame
                        affected.add(str(frame[1]) if len(frame) > 1 else "unknown")
                self._log.warning("%s dropped %d value(s) and %d frame(s) that could not be "
                                  "encoded as JSON, node(s) %s: %s",
                                  self.name, dropped_values, dropped_frames,
                                  ",".join(sorted(affected)), ex)
                databuffer = sanitised
                # Return True so that flush() clears the dropped frames from the
                # buffer rather than retrying a batch that can never succeed.
                if not databuffer:
                    return True
                number_of_frames = len(databuffer)
                try:
                    data_string = json.dumps(databuffer, separators=(',', ':'), allow_nan=False)
                except (ValueError, TypeError) as ex:
                    self._log.warning("%s discarding batch of %d frame(s), unable to encode as JSON: %s",
                                      self.name, number_of_frames, ex)
                    return True

            # Prepare URL string of the form
            # http://domain.tld/emoncms/input/bulk.json?apikey=12345
            # &data=[[0,10,82,23],[5,10,82,23],[10,10,82,23]]
            # &sentat=15' (requires emoncms >= 8.0)

            # time that the request was sent at
            sentat = int(time.time())
            
            # Construct post_url (without apikey)
            post_url = self._settings['url'] + '/input/bulk.json?sentat='+str(sentat)
            
            # If sendnames enabled then always compress:
            if self._settings['sendnames']:
                self._settings['compress'] = True
            
            # Compress if enabled
            if self._settings['compress']:
                json_str_size = len(data_string)
                # Compress data and encode as hex string.
                compressed = zlib.compress(data_string.encode())
                compression_ratio = len(compressed) / json_str_size
                # Only use compression if it makes sense!
                if compression_ratio<1.0:
                    post_body = compressed
                    # Set compression flag (cb = compression binary).
                    post_url = post_url + "&cb=1"
                    self._log.info("sending: %s (%d bytes of data, %d frames, compressed)", post_url, len(post_body),number_of_frames)
                    self._log.info("compression ratio: %d%%",compression_ratio*100)
                else: 
                    post_body = {'data': data_string}
                    self._log.info("sending: %s (%d bytes of data, %d frames, uncompressed)", post_url, len(data_string),number_of_frames)
                    self._log.info("compression ratio: %d%%, sent original",compression_ratio*100)
            else: 
                post_body = {'data': data_string}
                self._log.info("sending: %s (%d bytes of data, %d frames, uncompressed)", post_url, len(data_string),number_of_frames)
            
            try:
                st = time.time()
                reply = self.session.post(post_url, post_body, timeout=60, headers={'Authorization': 'Bearer '+self._settings['apikey']})
                dt = (time.time()-st)*1000
            except requests.exceptions.RequestException as ex:
                # No usable reply at all: server down, DNS failure, connection
                # refused, timeout, TLS error. Always keep the data, this is
                # precisely what the buffer is for.
                self._log.warning("%s couldn't send to server: %s", self.name, ex)
                self._schedule_retry()
                return False

            return self._process_reply(reply, dt, number_of_frames)
        
        # Sends status to myip module if enabled
        if self._settings['sendstatus']:
            post_url = self._settings['url'] + '/myip/set.json?apikey='
            self._log.info("sending: " + post_url + "E-M-O-N-C-M-S-A-P-I-K-E-Y")
            post_url = post_url + self._settings['apikey']
            try:
                reply = self.session.get(post_url, timeout=60)
                reply.raise_for_status()
                # self._log.debug(reply.text)
            except requests.exceptions.RequestException as ex:
                self._log.warning("%s couldn't send myip status update to server: %s", self.name, ex)

        return True

    def set(self, **kwargs):
        """

        :param kwargs:
        :return:
        """

        super().set(**kwargs)

        for key, setting in self._cms_settings.items():
            #valid = False
            if key not in kwargs:
                setting = self._cms_settings[key]
            else:
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'apikey':
                if setting.lower().startswith('xxxx'):  # FIXME compare whole string to 'x'*32?
                    self._log.warning("Setting %s apikey: obscured", self.name)
                elif len(setting) == 32:
                    self._log.info("Setting %s apikey: set", self.name)
                elif setting == "":
                    self._log.info("Setting %s apikey: null", self.name)
                else:
                    self._log.warning("Setting %s apikey: invalid format", self.name)
                    continue
                self._settings[key] = setting
                # Next line will log apikey if uncommented (privacy ?)
                #self._log.debug("%s apikey: %s", self.name, setting)
                continue
            elif key == 'url' and setting.startswith("http"):
                self._log.info("Setting %s url: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'senddata':
                self._log.info("Setting %s senddata: %s", self.name, setting)
                self._settings[key] = int(setting)
                continue
            elif key == 'sendstatus':
                self._log.info("Setting %s sendstatus: %s", self.name, setting)
                self._settings[key] = int(setting)
                continue
            elif key == 'sendnames':
                self._log.info("Setting " + self.name + " sendnames: " + str(setting))
                self._settings[key] = bool(int(setting))
                continue
            elif key == 'compress':
                self._log.info("Setting " + self.name + " compress: " + str(setting))
                self._settings[key] = bool(int(setting))
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
