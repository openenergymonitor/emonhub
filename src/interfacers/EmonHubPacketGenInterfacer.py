import time
import requests
from Cargo import new_cargo
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubPacketGenInterfacer

Monitors a socket for data, typically from ethernet link

"""

class EmonHubPacketGenInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        """Initialize interfacer

        """

        # Initialization
        super().__init__(name)

        self._control_timestamp = 0
        self._control_interval = 5
        self._defaults.update({'interval': 5, 'datacode': 'b'})
        self._pg_settings = {'apikey': "", 'url': 'http://localhost/emoncms'}
        self._settings.update(self._pg_settings)

    def read(self):
        """Read data from the PacketGen emonCMS module.

        """
        t = time.time()

        if t - self._control_timestamp <= self._control_interval:
            return

        req = self._settings['url'] + \
              "/emoncms/packetgen/getpacket.json?apikey="

        # logged without apikey added for security
        self._log.info("requesting packet: " + req + "E-M-O-N-C-M-S-A-P-I-K-E-Y")

        try:
            packet = requests.get(req + self._settings['apikey']).json()
        except (ValueError, requests.exceptions.RequestException) as ex:
            self._log.warning("no packet returned: " + str(ex))
            return

        raw = ""
        values = []
        datacodes = []

        for v in packet:
            raw += str(v['value']) + " "
            values.append(int(v['value']))
            # PacketGen datatypes are 0, 1 or 2 for bytes, ints & bools
            # bools are currently read as bytes 0 & 1
            datacodes.append(['B', 'h', 'B'][v['type']])

        c = new_cargo(rawdata=raw)

        # Extract the Target id if one is expected
        if self._settings['targeted']:
            #setting = str(setting).capitalize()
            c.target = int(values[0])
            values = values[1:]
            datacodes = datacodes[1:]

        c.realdata = values
        c.realdatacodes = datacodes

        self._control_timestamp = t
        c.timestamp = t

        # Return a Payload object
        #x = new_cargo(realdata=data)
        #x.realdatacodes = datacodes
        return c


    def action(self):
        """Actions that need to be done on a regular basis.

        This should be called in main loop by instantiater.

        """

        t = time.time()

        # Keep in touch with PacketGen and update refresh time
        interval = int(self._settings['interval'])
        if interval:  # A value of 0 means don't do anything
            if t - self._interval_timestamp < interval:
                return

            try:
                z = requests.get(self._settings['url'] +
                                 "/emoncms/packetgen/getinterval.json?apikey="
                                 + self._settings['apikey']).text
                i = int(z[1:-1])
            except:
                self._log.info("request interval not returned")
                return

            if self._control_interval != i:
                self._control_interval = i
                self._log.info("request interval set to: " + str(i) + " seconds")

            self._interval_timestamp = t

    def set(self, **kwargs):
        """

        """

        for key, setting in self._pg_settings.items():
            # Decide which setting value to use
            if key in kwargs:
                setting = kwargs[key]
            else:
                setting = self._pg_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'apikey':
                if setting.lower().startswith('xxxx'):  # FIXME compare whole string to 'x'*32?
                    self._log.warning("Setting " + self.name + " apikey: obscured")
                elif len(setting) == 32:
                    self._log.info("Setting " + self.name + " apikey: set")
                elif setting == "":
                    self._log.info("Setting " + self.name + " apikey: null")
                else:
                    self._log.warning("Setting " + self.name + " apikey: invalid format")
                    continue
                self._settings[key] = setting
                # Next line will log apikey if uncommented (privacy ?)
                #self._log.debug(self.name + " apikey: " + str(setting))
                continue
            elif key == 'url' and setting.startswith("http"):
                self._log.info("Setting " + self.name + " url: " + setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super().set(**kwargs)
