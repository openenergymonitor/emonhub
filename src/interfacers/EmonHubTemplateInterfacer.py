import time
import json
from itertools import zip_longest
import Cargo
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubTemplateInterfacer

Template interfacer for use in development

"""

class EmonHubTemplateInterfacer(EmonHubInterfacer):

    def __init__(self, name, port_nb=50011):
        """Initialize Interfacer

        """

        # Initialization
        super().__init__(name)

        # add or alter any default settings for this interfacer
        # defaults previously defined in inherited emonhub_interfacer
        # here we are just changing the batchsize from 1 to 100
        # and the interval from 0 to 30
        # self._defaults.update({'batchsize': 100,'interval': 30})

        # This line will stop the default values printing to logfile at start-up
        self._settings.update(self._defaults)

        # Interfacer specific settings
        # (settings not included in the inherited EmonHubInterfacer)
        # The set method below is called from emonhub.py on
        # initialisation and settings change and copies the
        # interfacer specific settings over to _settings

        # read_interval is just an example setting here
        # and can be removed and replaced with applicable settings
        self._template_settings = {'read_interval': 10.0}

        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250

    def read(self):
        """Read data and process

        Return data as a list: [NodeID, val1, val2]

        """

        # create a new cargo object, set data values
        c = Cargo.new_cargo()

        # Example cargo data
        # An interfacer would typically at this point
        # read from a socket or serial port and decode
        # the read data before setting the cargo object
        # variables
        c.nodeid = "test"
        c.names = ["power1", "power2", "power3"]
        c.realdata = [100, 200, 300]

        # usually the serial port or socket will provide
        # a delay as the interfacer waits at this point
        # to read a line of data but for testing here
        # we slow it down.

        time.sleep(self._settings['read_interval'])

        return c

    def add(self, cargo):
        """Append data to buffer.

          format: {"emontx":{"power1":100,"power2":200,"power3":300}}

        """

        nodename = str(cargo.nodeid)
        if cargo.nodename:
            nodename = cargo.nodename

        f = {'node': nodename,
             'data': {}
            }

        # FIXME zip_longest mimics the previous behaviour of this code which
        # filled the gaps with a numeric string. However it's surely an error
        # to provide more data than the schema expects, so it should either
        # be an explicit error or silently dropped.
        # If that's the case all this code can be simplified to:
        # f['data'] = {name: value for name, value in zip(cargo.names, cargo.realdata)}
        for i, (name, value) in enumerate(zip_longest(cargo.names, cargo.realdata, fill_value=None), start=1):
            f['data'][name or str(i)] = value

        if cargo.rssi:
            f['data']['rssi'] = cargo.rssi

        self.buffer.storeItem(f)

    def _process_post(self, databuffer):
        """Send data to server/broker or other output

        """

        for frame in databuffer:
            # Here we might typically publish or post the data
            # via MQTT, HTTP a socket or other output
            self._log.debug("node = %s node_data = %s", frame['node'], json.dumps(frame['data']))

            # We could check for successful data receipt here
            # and return false to retry next time
            # if not success: return False

        return True

    def set(self, **kwargs):
        for key, setting in self._template_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._template_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'read_interval':
                self._log.info("Setting %s read_interval: %s", self.name, setting)
                self._settings[key] = float(setting)
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)
