import time, json, Cargo, requests
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubTeslaPowerWallInterfacer

Fetch Tesla Power Wall state of charge

"""

class EmonHubTeslaPowerWallInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        super().__init__(name)

        self._settings.update(self._defaults)

        # Interfacer specific settings
        self._template_settings = {'name': 'powerwall',
                                   'url': False,
                                   'readinterval': 10.0}

        # FIXME is there a good reason to reduce this from the default of 1000? If so, document it here.
        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250

        # Fetch first reading at one interval lengths time
        self._last_time = 0

    def read(self):
        # Request Power Wall data at user specified interval
        if time.time() - self._last_time >= self._settings['readinterval']:
            self._last_time = time.time()

            # If URL is set, fetch the SOC
            if self._settings['url']:
                # HTTP Request
                try:
                    reply = requests.get(self._settings['url'], timeout=int(self._settings['readinterval']), verify=False)
                    reply.raise_for_status()  # Raise an exception if status code isn't 200
                except requests.exceptions.RequestException as ex:
                    self._log.warning("%s couldn't send to server: %s", self.name, ex)

                jsonstr = reply.text.rstrip()
                self._log.debug("%s Request response: %s", self.name, jsonstr)

                # Decode JSON
                try:
                    data = json.loads(jsonstr)
                except Exception:  # FIXME Too general exception
                    self._log.warning("%s Invalid JSON", self.name)
                    return

                # Check if battery percentage key is in data object
                if not 'percentage' in data:
                    self._log.warning("%s Percentage key not found", self.name)
                    return

                # Create cargo object
                c = Cargo.new_cargo()
                c.nodeid = self._settings['name']
                c.names = ["soc"]
                c.realdata = [data['percentage']]
                return c

        # return empty if not time
        return

    def set(self, **kwargs):
        for key, setting in self._template_settings.items():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._template_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'readinterval':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = float(setting)
                continue
            elif key == 'name':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = setting
                continue
            elif key == 'url':
                self._log.info("Setting %s %s: %s", self.name, key, setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)

        # include kwargs from parent
        super().set(**kwargs)
