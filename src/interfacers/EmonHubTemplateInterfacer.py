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
        super(EmonHubTemplateInterfacer, self).__init__(name)

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
        self._template_settings = {'read_interval':10.0}
        
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
        c.names = ["power1","power2","power3"]
        c.realdata = [100,200,300]
        
        # usually the serial port or socket will provide
        # a delay as the interfacer waits at this point 
        # to read a line of data but for testing here
        # we slow it down.
        
        time.sleep(self._settings['read_interval'])
        
        return c

    def _process_post(self, cargodatabuffer):
        """Send data to server/broker or other output
        
        """
        
        for c in range(0,len(cargodatabuffer)):
            cargo = cargodatabuffer[c]
            
            # Example of producing key:value pairs
            # from the names and realdata cargo properties
            node_data = {}
            for i in range(0,len(cargo.realdata)):
                if i<len(cargo.names):
                    key = cargo.names[i]
                    value = cargo.realdata[i]
                    node_data[key] = value
            
            # Here we might typically publish or post the data
            # via MQTT, HTTP a socket or other output
            self._log.debug("node_data = "+json.dumps(node_data))
            
            
            # We could check for successful data receipt here 
            # and return false to retry next time     
            # if not success: return False
            
        return True     
            

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
            elif key == 'read_interval':
                self._log.info("Setting " + self.name + " read_interval: " + str(setting))
                self._settings[key] = float(setting)
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (str(setting), self.name, key))

        # include kwargs from parent
        super(EmonHubTemplateInterfacer, self).set(**kwargs)

