"""class EmonHubMqttConfigInterfacer

Configure EmonHub via MQTT

[[MQTTConfig]]

    Type = EmonHubMqttConfigInterfacer
    [[[init_settings]]]
        mqtt_host = 127.0.0.1
        mqtt_port = 1883
        mqtt_user = emonpi
        mqtt_passwd = emonpimqtt2016

    [[[runtimesettings]]]

"""
import time
import paho.mqtt.client as mqtt
from emonhub_interfacer import EmonHubInterfacer
import Cargo
import json

class EmonHubMqttInterfacer(EmonHubInterfacer):

    def __init__(self, name, mqtt_user=" ", mqtt_passwd=" ", mqtt_host="127.0.0.1", mqtt_port=1883):
        """Initialize interfacer

        """

        # Initialization
        super().__init__(name)

        self.init_settings.update({
            'mqtt_host': mqtt_host,
            'mqtt_port': mqtt_port,
            'mqtt_user': mqtt_user,
            'mqtt_passwd': mqtt_passwd
        })

        self._connected = False

        self._mqttc = mqtt.Client()
        self._mqttc.on_connect = self.on_connect
        self._mqttc.on_disconnect = self.on_disconnect
        self._mqttc.on_message = self.on_message
        self._mqttc.on_subscribe = self.on_subscribe

    def add(self, cargo):
        # pass not used
        return True


    def action(self):

        if not self._connected:
            self._log.info("Connecting to MQTT Server")
            try:
                self._mqttc.username_pw_set(self.init_settings['mqtt_user'], self.init_settings['mqtt_passwd'])
                self._mqttc.connect(self.init_settings['mqtt_host'], int(self.init_settings['mqtt_port']), 60)
            except Exception:
                self._log.info("Could not connect...")
                time.sleep(1.0)
        
        
        self._mqttc.loop(0)

    def on_connect(self, client, userdata, flags, rc):

        connack_string = {0: 'Connection successful',
                          1: 'Connection refused - incorrect protocol version',
                          2: 'Connection refused - invalid client identifier',
                          3: 'Connection refused - server unavailable',
                          4: 'Connection refused - bad username or password',
                          5: 'Connection refused - not authorised',
                         }

        if rc:
            self._log.warning(connack_string[rc])
        else:
            self._log.info("connection status: %s", connack_string[rc])
            self._connected = True
            # Subscribe to MQTT topics
            # self._mqttc.subscribe(str(self._settings["node_format_basetopic"]) + "tx/#")

        self._log.debug("CONACK => Return code: %d", rc)

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            self._log.info("Unexpected disconnection")
            self._connected = False

    def on_subscribe(self, mqttc, obj, mid, granted_qos):
        self._log.info("on_subscribe")

    def on_message(self, client, userdata, msg):
        topic_parts = msg.topic.split("/")
    
        # log info topic and message
        self._log.info("topic: %s, message: %s", msg.topic, msg.payload)
                                

    def set(self, **kwargs):
        super().set(**kwargs)

        for key, setting in self._mqtt_settings.items():
            if key not in kwargs:
                setting = self._mqtt_settings[key]
            else:
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
