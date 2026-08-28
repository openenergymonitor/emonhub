"""class EmonHubEmoncmsHTTPInterfacer
"""
import time
import json
import math
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

    def _process_post(self, databuffer):
        """Send data to server."""

        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 250 ...]]

        if 'apikey' not in self._settings or len(str(self._settings['apikey'])) != 32 \
                or str(self._settings['apikey']).lower() == 'x' * 32:
            # Return true to clear buffer if the apikey is not set
            return True

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
            
            result = False
            try:
                st = time.time()
                reply = self.session.post(post_url, post_body, timeout=60, headers={'Authorization': 'Bearer '+self._settings['apikey']})
                dt = (time.time()-st)*1000
                reply.raise_for_status()  # Raise an exception if status code isn't 200
                result = reply.text
            except requests.exceptions.RequestException as ex:
                self._log.warning("%s couldn't send to server: %s", self.name, ex)
                return False

            if result == 'ok':
                self._log.debug("acknowledged receipt with '%s' from %s (%d ms)", result, self._settings['url'], dt)
                return True
            else:
                self._log.warning("send failure: wanted 'ok' but got '%s'", result)
                return False
        
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
