"""class EmonHubMqttSubsciberInterfacer

"""
import time
import paho.mqtt.client as mqtt
from emonhub_interfacer import EmonHubInterfacer
import Cargo

class EmonHubMqttSubsciberInterfacer(EmonHubInterfacer):

    def __init__(self, name, mqtt_user=" ", mqtt_passwd=" ", mqtt_host="127.0.0.1", mqtt_port=1883):
        """Initialize interfacer

        """
        
        # Initialization
        super(EmonHubMqttSubsciberInterfacer, self).__init__(name)

        # set the default setting values for this interfacer
        self._defaults.update({'datacode': '0'})
        self._settings.update(self._defaults)
        
        # Add any MQTT specific settings
        self._mqtt_settings = {
            'basetopic': 'emon',
            'topics': ''
        }
        self._settings.update(self._mqtt_settings)
        
        self.init_settings.update({
            'mqtt_host':mqtt_host, 
            'mqtt_port':mqtt_port,
            'mqtt_user':mqtt_user,
            'mqtt_passwd':mqtt_passwd
        })

        self._connected = False          
                  
        self._mqttc = mqtt.Client()
        self._mqttc.on_connect = self.on_connect
        self._mqttc.on_disconnect = self.on_disconnect
        self._mqttc.on_message = self.on_message
        self._mqttc.on_subscribe = self.on_subscribe
        
        self._log.info("Connecting to MQTT Server")
        try:
            # Use MQTTs if port set to 8883
            if int(self.init_settings['mqtt_port'])==8883:
                self._mqttc.tls_set(ca_certs="/usr/share/ca-certificates/mozilla/DST_Root_CA_X3.crt")
            self._mqttc.username_pw_set(self.init_settings['mqtt_user'], self.init_settings['mqtt_passwd'])
            self._mqttc.connect(self.init_settings['mqtt_host'], self.init_settings['mqtt_port'], 60)
        except:
            self._log.info("Could not connect...")
                
    def action(self):
        """

        :return:
        """
        self._mqttc.loop(0)
        
    def on_connect(self, client, userdata, flags, rc):
        
        connack_string = {0:'Connection successful',
                          1:'Connection refused - incorrect protocol version',
                          2:'Connection refused - invalid client identifier',
                          3:'Connection refused - server unavailable',
                          4:'Connection refused - bad username or password',
                          5:'Connection refused - not authorised'}

        if rc:
            self._log.warning(connack_string[rc])
        else:
            self._log.info("connection status: "+connack_string[rc])
            self._connected = True
            
            # Subscribe to MQTT topics
            topics = self._settings["topics"]
            if topics!='':
                #for topic in topics:  
                self._log.info("subscribing to: "+str(topics))
                self._mqttc.subscribe(str(topics))
            else:
                self._mqttc.subscribe(str(self._settings["basetopic"])+"/#")
            
            
        self._log.debug("CONACK => Return code: "+str(rc))
        
    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            self._log.info("Unexpected disconnection")
            self._connected = False
        
    def on_subscribe(self, mqttc, obj, mid, granted_qos):
        self._log.info("on_subscribe")
        
    def on_message(self, client, userdata, msg):
        
        try:
            value = float(msg.payload)
        except ValueError:
            value = "invalid"
            
        if value!="invalid":
        
            rxc = Cargo.new_cargo(realdata=[value])

            topic_parts = msg.topic.split("/")
            
            # Remove basetopic
            topic = msg.topic
            topic = topic.replace(self._settings["basetopic"]+"/","")
            
            # Split topic
            topic_parts = topic.split("/")
            rxc.nodeid = topic_parts[0]
            
            # remove node name
            topic_parts.pop(0)
            
            # create input name
            rxc.names = []
            rxc.names.append("_".join(topic_parts))

            self._log.debug("Message received: "+str(rxc.nodeid)+" "+str(rxc.names[0])+" "+str(msg.payload))
            
            # Add to pub channel
            for channel in self._settings["pubchannels"]:
                # Initialize channel if needed
                if not channel in self._pub_channels:
                    self._pub_channels[channel] = []
                # Add cargo item to channel
                self._pub_channels[channel].append(rxc)
            
                                
    def set(self, **kwargs):
        """

        :param kwargs:
        :return:
        """
        
        super (EmonHubMqttSubsciberInterfacer, self).set(**kwargs)

        for key, setting in self._mqtt_settings.iteritems():
            #valid = False
            if not key in kwargs.keys():
                setting = self._mqtt_settings[key]
            else:
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'basetopic':
                self._log.info("Setting " + self.name + " basetopic: " + setting)
                self._settings[key] = setting
                continue
            elif key == 'topics':
                self._log.info("Setting " + self.name + " topics: " + setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s" % (setting, self.name, key))
                
