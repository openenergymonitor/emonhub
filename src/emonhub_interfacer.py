"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import time
import logging
import threading
import traceback
import requests

import emonhub_coder as ehc
import emonhub_buffer as ehb

"""class EmonHubInterfacer

Monitors a data source.

This almost empty class is meant to be inherited by subclasses specific to
their data source.

"""

def log_exceptions_from_class_method(f):
    def wrapper(*args):
        self = args[0]
        try:
            return f(*args)
        except:
            self._log.warning("Exception caught in " + self.name + " thread. " + traceback.format_exc())
    return wrapper

class EmonHubInterfacer(threading.Thread):
    def __init__(self, name):
        # Initialise logger
        self._log = logging.getLogger("EmonHub")

        # Initialise thread
        super().__init__()
        self.setName(name)

        # Initialise settings
        self._defaults = {'pause': 'off',
                          'interval': 0,
                          'datacode': '0',
                          'scale': '1',
                          'timestamped': False,
                          'targeted': False,
                          'nodeoffset': '0',
                          'pubchannels': [],
                          'subchannels': [],
                          'batchsize': '1'}

        self.init_settings = {}
        self._settings = {}

        # Initialise message queue
        self._sub_channels = {}
        self._pub_channels = {}

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)

        # Initialize interval timer's "started at" timestamp
        self._interval_timestamp = 0

        buffer_type = "memory"
        buffer_size = 1000

        # Create underlying buffer implementation
        self.buffer = ehb.getBuffer(buffer_type)(name, buffer_size)

        # set an absolute upper limit for number of items to process per post
        # number of items posted is the lower of this item limit, buffer_size, or the
        # batchsize, as set in reporter settings or by the default value.
        self._item_limit = buffer_size

        # create a stop
        self.stop = False

    @log_exceptions_from_class_method
    def run(self):
        """
        Run the interfacer.
        Any regularly performed tasks actioned here along with passing received values

        """
        while not self.stop:

            # Only read if there is a pub channel defined for the interfacer
            if len(self._settings["pubchannels"]):
                # Read the input and process data if available
                rxc = self.read()
                if rxc:
                    rxc = self._process_rx(rxc)
                    if rxc:
                        for channel in self._settings["pubchannels"]:
                            self._log.debug(str(rxc.uri) + " Sent to channel(start)' : " + str(channel))

                            # Initialise channel if needed
                            if channel not in self._pub_channels:
                                self._pub_channels[channel] = []

                            # Add cargo item to channel
                            self._pub_channels[channel].append(rxc)

                            self._log.debug(str(rxc.uri) + " Sent to channel(end)' : " + str(channel))

            # Subscriber channels
            for channel in self._settings["subchannels"]:
                if channel in self._sub_channels:
                    # FIXME should be: while self._sub_channels[channel]
                    for _ in range(len(self._sub_channels[channel])):
                        # FIXME pop(0) has O(n) complexity. Can we use pop's default of last?
                        frame = self._sub_channels[channel].pop(0)
                        self.add(frame)

            # Don't loop too fast
            time.sleep(0.1)
            # Action reporter tasks
            self.action()

    def add(self, cargo):
        """Append data to buffer.

        data (list): node and values (eg: '[node,val1,val2,...]')

        """

        # Create a frame of data in "emonCMS format"
        f = []
        try:
            f.append(cargo.timestamp)
            f.append(cargo.nodeid)
            # FIXME replace with f.extend(cargo.realdata)
            for i in cargo.realdata:
                f.append(i)
            if cargo.rssi:
                f.append(cargo.rssi)

            # self._log.debug(str(cargo.uri) + " adding frame to buffer => "+ str(f))

        except:
            self._log.warning("Failed to create emonCMS frame " + str(f))

        # self._log.debug(str(carg.ref) + " added to buffer =>"
        #                 + " time: " + str(carg.timestamp)
        #                 + ", node: " + str(carg.node)
        #                 + ", data: " + str(carg.data))

        # databuffer is of format:
        # [[timestamp, nodeid, datavalues][timestamp, nodeid, datavalues]]
        # [[1399980731, 10, 150, 3450 ...]]

        # databuffer format can be overwritten by interfacer

        self.buffer.storeItem(f)

    def read(self):
        """Read raw data from interface and pass for processing.
        Specific version to be created for each interfacer
        Returns an EmonHubCargo object
        """
        pass


    def send(self, cargo):
        """Send data from interface.
        Specific version to be created for each interfacer
        Accepts an EmonHubCargo object
        """
        pass


    def action(self):
        """

        :return:
        """

        # pause output if 'pause' set to 'all' or 'out'
        if 'pause' in self._settings \
                and str(self._settings['pause']).lower() in ['all', 'out']:
            return

        # If an interval is set, check if that time has passed since last post
        if int(self._settings['interval']) \
                and time.time() - self._interval_timestamp < int(self._settings['interval']):
            return
        else:
            # Then attempt to flush the buffer
            self.flush()

    def flush(self):
        """Send oldest data in buffer, if any."""

        # Buffer management
        # If data buffer not empty, send a set of values
        if self.buffer.hasItems():
            self._log.debug("Buffer size: " + str(self.buffer.size()))

            max_items = int(self._settings['batchsize'])
            if max_items > self._item_limit:
                max_items = self._item_limit
            elif max_items <= 0:
                return

            databuffer = self.buffer.retrieveItems(max_items)
            retrievedlength = len(databuffer)
            if self._process_post(databuffer):
                # In case of success, delete sample set from buffer
                self.buffer.discardLastRetrievedItems(retrievedlength)
            # log the time of last successful post
            # slow down retry rate in the case where the last attempt failed
            # stops continuous retry attempts filling up the log
            self._interval_timestamp = time.time()


    def _process_post(self, data):
        """
        To be implemented in subclass.

        :return: True if data posted successfully and can be discarded
        """
        pass

    def _send_post(self, post_url, post_body=None):
        """

        :param post_url:
        :param post_body:
        :return: the received reply if request is successful
        """
        """Send data to server.

        data (list): node and values (eg: '[node,val1,val2,...]')
        time (int): timestamp, time when sample was recorded

        return True if data sent correctly

        """

        try:
            if post_body:
                reply = requests.post(post_url, post_body)
            else:
                reply = requests.get(post_url)
            reply.raise_for_status()  # Raise an exception if status code isn't 200
            return reply.text
        except requests.exceptions.RequestException as ex:
            self._log.warning(self.name + " couldn't send to server: " + str(ex))

    def _process_rx(self, cargo):
        """Process a frame of data

        f (string): 'NodeID val1 val2 ...'

        This function splits the string into numbers and check its validity.

        'NodeID val1 val2 ...' is the generic data format. If the source uses
        a different format, override this method.

        Return data as a list: [NodeID, val1, val2]

        """

        # Log data
        self._log.debug(str(cargo.uri) + " NEW FRAME : " + str(cargo.rawdata))

        rxc = cargo
        decoded = []
        node = str(rxc.nodeid)
        datacode = True

        # Discard if data is non-existent
        if len(rxc.realdata) < 1:
            self._log.warning(str(cargo.uri) + " Discarded RX frame 'string too short' : " + str(rxc.realdata))
            return False

        # Discard if anything non-numerical found
        try:
            [float(val) for val in rxc.realdata]
        except Exception:
            self._log.warning(str(cargo.uri) + " Discarded RX frame 'non-numerical content' : " + str(rxc.realdata))
            return False

        # Discard if first value is not a valid node id
        # n = float(rxc.realdata[0])
        # if n % 1 != 0 or n < 0 or n > 31:
        #     self._log.warning(str(cargo.uri) + " Discarded RX frame 'node id outside scope' : " + str(rxc.realdata))
        #     return False

        # Data whitening uses for ensuring rfm sync
        if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'whitening' in ehc.nodelist[node]['rx']:
            whitening = ehc.nodelist[node]['rx']['whitening']
            if whitening is True or whitening == "1":
                for i in range(len(rxc.realdata)):
                    rxc.realdata[i] = rxc.realdata[i] ^ 0x55

        # check if node is listed and has individual datacodes for each value
        if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'datacodes' in ehc.nodelist[node]['rx']:
            # fetch the string of datacodes
            datacodes = ehc.nodelist[node]['rx']['datacodes']

            # fetch a string of data sizes based on the string of datacodes
            datasizes = []
            for code in datacodes:
                datasizes.append(ehc.check_datacode(str(code)))
            # Discard the frame & return 'False' if it doesn't match the summed datasizes
            if len(rxc.realdata) != sum(datasizes):
                self._log.warning(str(rxc.uri) + " RX data length: " + str(len(rxc.realdata)) +
                                  " is not valid for datacodes " + str(datacodes))
                return False
            else:
                # Determine the expected number of values to be decoded
                count = len(datacodes)
                # Set decoder to "Per value" decoding using datacode 'False' as flag
                datacode = False
        else:
            # if node is listed, but has only a single default datacode for all values
            if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'datacode' in ehc.nodelist[node]['rx']:
                datacode = ehc.nodelist[node]['rx']['datacode']
            else:
                # when node not listed or has no datacode(s) use the interfacers default if specified
                datacode = self._settings['datacode']
            # Ensure only int 0 is passed not str 0
            if datacode == '0':
                datacode = 0
            # when no (default)datacode(s) specified, pass string values back as numerical values
            if not datacode:
                for val in rxc.realdata:
                    if float(val) % 1 != 0:
                        val = float(val)
                    else:
                        val = int(float(val))
                    decoded.append(val)
            # Discard frame if total size is not an exact multiple of the specified datacode size.
            elif len(rxc.realdata) % ehc.check_datacode(datacode) != 0:
                self._log.warning(str(rxc.uri) + " RX data length: " + str(len(rxc.realdata)) +
                                  " is not valid for datacode " + str(datacode))
                return False
            else:
            # Determine the number of values in the frame of the specified code & size
                count = len(rxc.realdata) // ehc.check_datacode(datacode)

        # Decode the string of data one value at a time into "decoded"
        if not decoded:
            bytepos = 0
            for i in range(count):
                # Use single datacode unless datacode = False then use datacodes
                dc = str(datacode)
                if not datacode:
                    dc = str(datacodes[i])
                # Determine the number of bytes to use for each value by it's datacode
                size = int(ehc.check_datacode(dc))
                try:
                    value = ehc.decode(dc, [int(v) for v in rxc.realdata[bytepos:bytepos+size]])
                except:
                    self._log.warning(str(rxc.uri) + " Unable to decode as values incorrect for datacode(s)")
                    return False
                bytepos += size
                decoded.append(value)

        # check if node is listed and has individual scales for each value
        if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'scales' in ehc.nodelist[node]['rx']:
            scales = ehc.nodelist[node]['rx']['scales']
            # === Removed check for scales length so that failure mode is more gracious ===
            # Discard the frame & return 'False' if it doesn't match the number of scales
            # if len(decoded) != len(scales):
            #     self._log.warning(str(rxc.uri) + " Scales " + str(scales) + " for RX data : " + str(rxc.realdata) + " not suitable " )
            #     return False
            # else:
                  # Determine the expected number of values to be decoded
                  # Set decoder to "Per value" scaling using scale 'False' as flag
            #     scale = False
            if len(scales) > 1:
                scale = False
            else:
                scale = "1"
        else:
            # if node is listed, but has only a single default scale for all values
            if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'scale' in ehc.nodelist[node]['rx']:
                scale = ehc.nodelist[node]['rx']['scale']
            else:
            # when node not listed or has no scale(s) use the interfacers default if specified
                scale = self._settings['scale']

        if scale != "1":
            # FIXME replace with zip
            for i in range(len(decoded)):
                x = scale
                if not scale:
                    if i < len(scales):
                        x = scales[i]
                    else:
                        x = 1

                if x != "1":
                    val = decoded[i] * float(x)
                    if val % 1 == 0:
                        decoded[i] = int(val)
                    else:
                        decoded[i] = float(val)

        rxc.realdata = decoded
        names = rxc.names

        if node in ehc.nodelist and 'rx' in ehc.nodelist[node] and 'names' in ehc.nodelist[node]['rx']:
            names = ehc.nodelist[node]['rx']['names']
        rxc.names = names

        nodename = False
        if node in ehc.nodelist and 'nodename' in ehc.nodelist[node]:
            nodename = ehc.nodelist[node]['nodename']
        rxc.nodename = nodename

        if not rxc:
            return False
        self._log.debug(str(rxc.uri) + " Timestamp : " + str(rxc.timestamp))
        self._log.debug(str(rxc.uri) + " From Node : " + str(rxc.nodeid))
        if rxc.target:
            self._log.debug(str(rxc.uri) + " To Target : " + str(rxc.target))
        self._log.debug(str(rxc.uri) + "    Values : " + str(rxc.realdata))
        if rxc.rssi:
            self._log.debug(str(rxc.uri) + "      RSSI : " + str(rxc.rssi))

        return rxc


    def _process_tx(self, cargo):
        """Prepare data for outgoing transmission.
        cargo is passed through this chain of processing to scale
        and then break the real values down into byte values,
        Uses the datacode data if available.

        DO NOT OVER-WRITE THE "REAL" VALUE DATA WITH ENCODED DATA !!!
        there may be other threads that need to use cargo.realdata to
        encode data for other targets.

        New "encoded" data is stored as a list of {interfacer:encoded-data} dicts.

        Returns cargo.
        """

        txc = cargo
        scaled = []
        encoded = []

        # Normal operation is dest from txc.nodeid
        if txc.target:
            dest = str(txc.target)
            # self._log.info("dest from txc.target: " + dest)
        else:
            dest = str(txc.nodeid)
            # self._log.info("dest from txc.nodeid: " + dest)

        # self._log.info("Target: " + dest)
        # self._log.info("Realdata: " + json.dumps(txc.realdata))

        # check if node is listed and has individual scales for each value
        if dest in ehc.nodelist and 'tx' in ehc.nodelist[dest] and 'scales' in ehc.nodelist[dest]['tx']:
            scales = ehc.nodelist[dest]['tx']['scales']
            # Discard the frame & return 'False' if it doesn't match the number of scales
            if len(txc.realdata) != len(scales):
                self._log.warning(str(txc.uri) + " Scales " + str(scales) + " for RX data : " + str(txc.realdata) +
                                  " not suitable ")
                return False
            else:
                # Determine the expected number of values to be decoded

                # Set decoder to "Per value" scaling using scale 'False' as flag
                scale = False
        else:
            # if node is listed, but has only a single default scale for all values
            if dest in ehc.nodelist and 'tx' in ehc.nodelist[dest] and 'scale' in ehc.nodelist[dest]['tx']:
                scale = ehc.nodelist[dest]['tx']['scale']
            else:
            # when node not listed or has no scale(s) use the interfacers default if specified
                if 'scale' in self._settings:
                    scale = self._settings['scale']
                else:
                    scale = "1"

        if scale == "1":
            scaled = txc.realdata
        else:
            for i in range(len(txc.realdata)):
                x = scale
                if not scale:
                    x = scales[i]
                if x == "1":
                    val = txc.realdata[i]
                else:
                    val = float(txc.realdata[i]) / float(x)
                    if val % 1 == 0:
                        val = int(val)
                scaled.append(val)

        # self._log.info("Scaled: " + json.dumps(scaled))

        # check if node is listed and has individual datacodes for each value
        if dest in ehc.nodelist and 'tx' in ehc.nodelist[dest] and 'datacodes' in ehc.nodelist[dest]['tx']:

            # fetch the string of datacodes
            datacodes = ehc.nodelist[dest]['tx']['datacodes']

            # fetch a string of data sizes based on the string of datacodes
            datasizes = []
            for code in datacodes:
                datasizes.append(ehc.check_datacode(str(code)))
            # Discard the frame & return 'False' if it doesn't match the summed datasizes
            if len(scaled) != len(datasizes):
                self._log.warning(str(txc.uri) + " TX datacodes: " + str(datacodes) +
                                  " are not valid for values " + str(scaled))
                return False
            else:
                # Determine the expected number of values to be decoded
                count = len(scaled)
                # Set decoder to "Per value" decoding using datacode 'False' as flag
                datacode = False
        else:
            # if node is listed, but has only a single default datacode for all values
            if dest in ehc.nodelist and 'tx' in ehc.nodelist[dest] and 'datacode' in ehc.nodelist[dest]['tx']:
                datacode = ehc.nodelist[dest]['tx']['datacode']
            else:
            # when node not listed or has no datacode(s) use the interfacers default if specified
                if 'datacode' in self._settings:
                    datacode = self._settings['datacode']
                else:
                    datacode = "h"

            # Ensure only int 0 is passed not str 0
            if datacode == '0':
                datacode = 0
            # when no (default)datacode(s) specified, pass string values back as numerical values
            if not datacode:
                encoded.append(dest)

                for val in scaled:
                    if float(val) % 1 != 0:
                        val = float(val)
                    else:
                        val = int(float(val))
                    encoded.append(val)
            # Discard frame if total size is not an exact multiple of the specified datacode size.
            # elif len(data) * ehc.check_datacode(datacode) != 0:
            #     self._log.warning(str(uri) + " TX data length: " + str(len(data)) +
            #                       " is not valid for datacode " + str(datacode))
            #     return False
            else:
            # Determine the number of values in the frame of the specified code & size
                count = len(scaled) #/ ehc.check_datacode(datacode)

        if not encoded:
            encoded.append(dest)
            for i in range(count):
                # Use single datacode unless datacode = False then use datacodes
                dc = str(datacode)
                if not datacode:
                    dc = str(datacodes[i])

                for b in ehc.encode(dc, int(scaled[i])):
                    encoded.append(b)

        # self._log.info("Encoded: "+json.dumps(encoded))

        txc.encoded.update({self.getName():encoded})
        return txc

    def set(self, **kwargs):
        """Set configuration parameters.

        **kwargs (dict): settings to be sent. Example:
        {'setting_1': 'value_1', 'setting_2': 'value_2'}

        pause (string): pause status
            'pause' = all  pause Interfacer fully, nothing read, processed or posted.
            'pause' = in   pauses the input only, no input read performed
            'pause' = out  pauses output only, input is read, processed but not posted to buffer
            'pause' = off  pause is off and Interfacer is fully operational (default)

        """
    #def setall(self, **kwargs):

        for key, setting in self._defaults.items():
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._defaults[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'pause' and str(setting).lower() in ['all', 'in', 'out', 'off']:
                pass
            elif key in ['interval', 'batchsize'] and setting.isdigit():
                pass
            elif key == 'nodeoffset' and str(setting).isdigit():
                pass
            elif key == 'datacode' and str(setting) in ['0', 'b', 'B', 'h', 'H', 'L', 'l', 'f']:
                pass
            elif key == 'scale' and (int(setting == 1) or not int(setting % 10)):
                pass
            elif key == 'timestamped' and str(setting).lower() in ['true', 'false']:
                setting = str(setting).lower() == "true"
            elif key == 'targeted' and str(setting).lower() in ['true', 'false']:
                setting = str(setting).lower() == "true"
            elif key == 'pubchannels':
                pass
            elif key == 'subchannels':
                pass
            else:
                self._log.warning("In interfacer set '%s' is not a valid setting for %s: %s" % (str(setting), self.name, key))
                continue
            self._settings[key] = setting
            self._log.debug("Setting " + self.name + " " + key + ": " + str(setting))


"""class EmonHubInterfacerInitError

Raise this when init fails.

"""
class EmonHubInterfacerInitError(Exception):
    pass
