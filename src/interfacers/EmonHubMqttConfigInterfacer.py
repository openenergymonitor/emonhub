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
from configobj import ConfigObj


class EmonHubMqttConfigInterfacer(EmonHubInterfacer):

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
        self._last_connect_attempt = 0

        self._mqttc = mqtt.Client()
        self._mqttc.on_connect = self.on_connect
        self._mqttc.on_disconnect = self.on_disconnect
        self._mqttc.on_message = self.on_message
        self._mqttc.on_subscribe = self.on_subscribe

    def add(self, cargo):
        # pass not used
        return True


    def action(self):

        if not self._connected and time.time() - self._last_connect_attempt > 10:
            self._last_connect_attempt = time.time()
            try:
                self._mqttc.username_pw_set(self.init_settings['mqtt_user'], self.init_settings['mqtt_passwd'])
                self._mqttc.connect(self.init_settings['mqtt_host'], int(self.init_settings['mqtt_port']), 60)
            except Exception:
                self._log.info("Could not connect to MQTT config server %s:%s", self.init_settings['mqtt_host'], self.init_settings['mqtt_port'])
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
            self._mqttc.subscribe("emonhub/request/#")

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
        
        # Request emonhub/request/device_1  { "command": "get_config" }
        if topic_parts[1] == "request":
            if topic_parts[2] == "device_1":
                if json.loads(msg.payload.decode('utf-8'))['command'] == "get_config":
                    # Send config
                    self.load_config_file(self._config_path)
                    self._mqttc.publish("emonhub/response/device_1", json.dumps(self.config), qos=0)
                                

    def load_config_file(self, filename):
        # Initialize attribute settings as a ConfigObj instance
        try:
            self.config = ConfigObj(filename, file_error=True)

            # Check the settings file sections
            self.config['hub']
            self.config['interfacers']
        except IOError as e:
            raise EmonHubSetupInitError(e)
        except SyntaxError as e:
            raise EmonHubSetupInitError(
                'Error parsing config file "%s": ' % filename + str(e))
        except KeyError as e:
            raise EmonHubSetupInitError(
                'Configuration file error - section: ' + str(e))


    def set(self, **kwargs):
        super().set(**kwargs)


    def set_config_path(self, path):
        self._config_path = path