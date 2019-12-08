import time, json, Cargo
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

        f = {}
        f['node'] = nodename
        f['data'] = {}

        # FIXME replace with zip
        for i in range(len(cargo.realdata)):
            name = str(i + 1)
            if i < len(cargo.names):
                name = cargo.names[i]
            value = cargo.realdata[i]
            f['data'][name] = value

        if cargo.rssi:
            f['data']['rssi'] = cargo.rssi

        self.buffer.storeItem(f)

    def _process_post(self, databuffer):
        """Send data to server/broker or other output

        """

        for frame in databuffer:
            # Here we might typically publish or post the data
            # via MQTT, HTTP a socket or other output
            self._log.debug("node = " + frame['node'] + " node_data = " + json.dumps(frame['data']))

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
                self._log.info("Setting " + self.name + " read_interval: " + str(setting))
                self._settings[key] = float(setting)
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super().set(**kwargs)
