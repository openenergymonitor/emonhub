import time, json, Cargo, urllib2, ssl
from emonhub_interfacer import EmonHubInterfacer

"""class EmonHubTeslaPowerWallInterfacer

Fetch Tesla Power Wall state of charge

"""

class EmonHubTeslaPowerWallInterfacer(EmonHubInterfacer):

    def __init__(self, name):
        """Initialize Interfacer
        
        """

        # Initialization
        super(EmonHubTeslaPowerWallInterfacer, self).__init__(name)

        self._settings.update(self._defaults)

        # Interfacer specific settings
        self._template_settings = {'name':'powerwall', 'url':False, 'readinterval':10.0}
        
        # set an absolute upper limit for number of items to process per post
        self._item_limit = 250
        
        # Fetch first reading at one interval lengths time
        self._last_time = time.time()

    def read(self):
        """

        """
        
        # Request Power Wall data at user specified interval
        if (time.time()-self._last_time)>=self._settings['readinterval']:
            self._last_time = time.time()

            # If URL is set, fetch the SOC
            if self._settings['url']:
                # HTTP Request
                try:
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
                    response = urllib2.urlopen(self._settings['url'], context=ctx, timeout=int(self._settings['readinterval']))
                except urllib2.HTTPError as e:
                    self._log.warning("HTTPError: "+str(e.code))
                    return
                except urllib2.URLError as e:
                    self._log.warning("URLError: "+str(e.reason))
                    return
                except httplib.HTTPException:
                    self._log.warning("HTTPException")
                    return
                except Exception:
                    import traceback
                    self._log.warning("Exception: "+traceback.format_exc())
                    return
               
                jsonstr = response.read().rstrip()
                self._log.debug("Request response: "+str(jsonstr))
                
                # Decode JSON
                try:
                    data = json.loads(jsonstr)
                except:
                    self._log.warning("Invalid JSON")
                    return
            
                # Check if battery percentage key is in data object
                if not 'percentage' in data:
                    self._log.warning("Percentage key not found")
                    return
                
                # Extract SOC value
                soc = data['percentage']
 
                # Create cargo object
                c = Cargo.new_cargo()
                c.nodeid = self._settings['name']
                c.names = ["soc"]
                c.realdata = [soc]
                return c
        
        # return empty if not time
        return

    def set(self, **kwargs):
        """

        """

        for key, setting in self._template_settings.iteritems():
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._template_settings[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'readinterval':
                self._log.info("Setting " + self.name + " readinterval: " + str(setting))
                self._settings[key] = float(setting)
                continue
            elif key == 'name':
                self._log.info("Setting " + self.name + " name: " + str(setting))
                self._settings[key] = setting
                continue
            elif key == 'url':
                self._log.info("Setting " + self.name + " url: " + str(setting))
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super(EmonHubTeslaPowerWallInterfacer, self).set(**kwargs)

