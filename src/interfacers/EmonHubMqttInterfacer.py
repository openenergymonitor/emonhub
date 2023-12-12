"""class EmonHubMqttGenInterfacer

Example emonhub configuration
[[MQTT]]

    Type = EmonHubMqttInterfacer
    [[[init_settings]]]
        mqtt_host = 127.0.0.1
        mqtt_port = 1883
        mqtt_user = emonpi
        mqtt_passwd = emonpimqtt2016

    [[[runtimesettings]]]
        subchannels = ToEmonCMS,

        # emonhub/rx/10/values format
        # Use with emoncms Nodes module
        node_format_enable = 1
        node_format_basetopic = emonhub/

        # emon/emontx/power1 format - use with Emoncms MQTT input
        # http://github.com/emoncms/emoncms/blob/master/docs/RaspberryPi/MQTT.md
        nodevar_format_enable = 1
        nodevar_format_basetopic = emon/

        # JSON format data that can have a timestamp
        timestamped = True
        node_JSON_enable = 1
        node_JSON_basetopic = emon/JSON/

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

        # set the default setting values for this interfacer
        self._defaults.update({'datacode': '0'})
        self._settings.update(self._defaults)

        # Add any MQTT specific settings
        self._mqtt_settings = {
            # emonhub/rx/10/values format - default emoncms nodes module
            'node_format_enable': 0,
            'node_format_basetopic': 'emonhub/',

            # nodes/emontx/power1 format
            'nodevar_format_enable': 0,
            'nodevar_format_basetopic': "nodes/",

            # JSON format
            'node_JSON_enable': 0,
            'node_JSON_basetopic': "emon/"
        }
        self._settings.update(self._mqtt_settings)

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
        """Append data to buffer.

        format: {"emontx":{"power1":100,"power2":200,"power3":300}}

        """

        nodename = str(cargo.nodeid)
        if cargo.nodename:
            nodename = cargo.nodename

        f = {}
        f['nodeid'] = cargo.nodeid
        f['node'] = nodename
        f['names'] = cargo.names
        f['data'] = cargo.realdata
        f['timestamp'] = cargo.timestamp

        if cargo.rssi:
            f['rssi'] = cargo.rssi

        # This basic QoS level 1 MQTT interfacer does not require buffering
        # therefore we call _process_post here directly with an array
        # containing only the one frame.

        # _process_post will never be called from the emonhub_interfacer
        # run > action > flush > _process_post chain as the buffer will
        # always be empty.

        # This is a bit of a hack, the final approach is currently being considered
        # as part of ongoing discussion on future direction of emonhub

        self._process_post([f])

        # To re-enable buffering comment the above three lines and uncomment the following
        # note that at preset _process_post will not handle buffered data correctly and
        # no time is transmitted to the subscribing clients

        # self.buffer.storeItem(f)

    def read(self):
        if not self._connected:
            self._log.info("Connecting to MQTT Server")
            try:
                self._mqttc.username_pw_set(self.init_settings['mqtt_user'], self.init_settings['mqtt_passwd'])
                self._mqttc.connect(self.init_settings['mqtt_host'], int(self.init_settings['mqtt_port']), 60)
            except Exception:
                self._log.info("Could not connect...")
                time.sleep(1.0)  # FIXME why sleep? we're just about to return True



    def _process_post(self, databuffer):
        if not self._connected:
            self._log.info("Connecting to MQTT Server")
            try:
                self._mqttc.username_pw_set(self.init_settings['mqtt_user'], self.init_settings['mqtt_passwd'])
                self._mqttc.connect(self.init_settings['mqtt_host'], int(self.init_settings['mqtt_port']), 60)
            except Exception:
                self._log.info("Could not connect...")
                time.sleep(1.0)  # FIXME why sleep? we're just about to return True

        else:
            frame = databuffer[0]
            nodename = frame['node']
            nodeid = frame['nodeid']

            # ----------------------------------------------------------
            # General MQTT format: emonhub/rx/emonpi/power1 ... 100
            # ----------------------------------------------------------
            if int(self._settings["nodevar_format_enable"]) == 1:
                # FIXME replace with zip
                for i in range(len(frame['data'])):
                    inputname = str(i + 1)
                    if i < len(frame['names']):
                        inputname = frame['names'][i]
                    value = frame['data'][i]

                    # Construct topic
                    topic = self._settings["nodevar_format_basetopic"] + nodename + "/" + inputname
                    payload = str(value)

                    self._log.debug("Publishing: %s %s", topic, payload)
                    result = self._mqttc.publish(topic, payload=payload, qos=2, retain=False)

                    if result[0] == 4:
                        self._log.info("Publishing error? returned 4")
                        return False

                # send rssi
                if 'rssi' in frame:
                    topic = self._settings["nodevar_format_basetopic"] + nodename + "/rssi"
                    payload = str(frame['rssi'])

                    self._log.debug("Publishing: %s %s", topic, payload)
                    result = self._mqttc.publish(topic, payload=payload, qos=2, retain=False)

                    if result[0] == 4:
                        self._log.info("Publishing error? returned 4")
                        return False

            # ----------------------------------------------------------
            # Emoncms nodes module format: emonhub/rx/10/values ... 100,200,300
            # ----------------------------------------------------------
            if int(self._settings["node_format_enable"]) == 1:
                topic = self._settings["node_format_basetopic"] + "rx/" + str(nodeid) + "/values"

                payload = ",".join(map(str, frame['data']))

                if 'rssi' in frame:
                    payload = payload + "," + str(frame['rssi'])

                self._log.info("Publishing 'node' formatted msg")
                self._log.debug("Publishing: %s %s", topic, payload)
                result = self._mqttc.publish(topic, payload=payload, qos=2, retain=False)

                if result[0] == 4:
                    self._log.info("Publishing error? returned 4")
                    return False

            # ----------------------------------------------------------
            # Emoncms JSON format: <basetopic>/<nodeid> {"key":Value, ... "time":<timestamp>}
            # ----------------------------------------------------------
            if int(self._settings["node_JSON_enable"]) == 1:
                topic = self._settings["node_JSON_basetopic"] + nodename
                payload = dict(zip(frame['names'], frame['data']))
                payload['time'] = frame['timestamp']
                if 'rssi' in frame:
                    payload['rssi'] = frame['rssi']

                payloadJSON = json.dumps(payload)

                self._log.debug("Publishing: " + topic + " " + payloadJSON)
                result = self._mqttc.publish(topic, payload=payloadJSON, qos=2, retain=False)

                if result[0] == 4:
                    self._log.info("Publishing error? returned 4")
                    return False

        return True

    def action(self):
        self._mqttc.loop(0)

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
            if len(self._settings["pubchannels"]) and not len(self._settings["subchannels"]):
                if int(self._settings["nodevar_format_enable"]) == 1:
                    self._log.info("subscribe "+str(self._settings["nodevar_format_basetopic"]))
                    self._mqttc.subscribe(str(self._settings["nodevar_format_basetopic"]))
                if int(self._settings["node_format_enable"]) == 1:
                    self._log.info("subscribe "+str(self._settings["node_format_basetopic"]))
                    self._mqttc.subscribe(str(self._settings["node_format_basetopic"]))
                if int(self._settings["node_JSON_enable"]) == 1:
                    self._log.info("subscribe "+str(self._settings["node_JSON_enable"]))
                    self._mqttc.subscribe(str(self._settings["node_JSON_basetopic"]))
                         
        self._log.debug("CONACK => Return code: %d", rc)

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            self._log.info("Unexpected disconnection")
            self._connected = False

    def on_subscribe(self, mqttc, obj, mid, granted_qos):
        self._log.info("on_subscribe")

    def on_message(self, client, userdata, msg):
        topic_parts = msg.topic.split("/")

        self._log.debug("Received topic:"+str(msg.topic))
        self._log.debug("Received payload:"+str(msg.payload.decode()))
          
        rxc = False
    
        # General MQTT format: emon/emonpi/power1 ... 100
        if int(self._settings["nodevar_format_enable"]) == 1:
            # if topic_parts[0] == self._settings["nodevar_format_basetopic"][:-1]:
                nodeid = topic_parts[1]
                variable_name = "_".join(topic_parts[2:])
                try:
                    value = float(msg.payload.decode())
                    realdata = [value]
                    rxc = Cargo.new_cargo(realdata=realdata)
                    rxc.nodeid = nodeid       
                    rxc.names = [variable_name]

                except Exception:
                    self._log.error("Payload format error")
            
        # Emoncms nodes module format: emon/tx/10/values ... 100,200,300
        if int(self._settings["node_format_enable"]) == 1:
            # if topic_parts[0] == self._settings["node_format_basetopic"][:-1]:
                if len(topic_parts)==4 and topic_parts[1] == "tx" and topic_parts[3] == "values":
                    nodeid = topic_parts[2]
                    payload = msg.payload.decode()
                    realdata = payload.split(",")
                    try:
                        for i in range(0,len(realdata)):
                            realdata[i] = float(realdata[i])
                        
                        rxc = Cargo.new_cargo(realdata=realdata)
                        rxc.nodeid = nodeid
                    except Exception:
                        self._log.error("Payload format error")        
                
        # JSON format: zigbeemqtt/temp1 {"battery":100,"humidity":80,"temperature":22,"voltage":3100}
        if int(self._settings["node_JSON_enable"]) == 1:
            # if topic_parts[0] == self._settings["node_JSON_basetopic"][:-1]:
                nodeid = topic_parts[1]
                json_string = msg.payload.decode()
                try:
                    json_data = json.loads(json_string)
                    names = []
                    values = []
                    for key in json_data:
                        names.append(key)
                        values.append(json_data[key])
                    rxc = Cargo.new_cargo(realdata=values)
                    rxc.nodeid = nodeid   
                    rxc.names = names
                except Exception:     
                    self._log.error("Payload JSON format error")                       
        if rxc:
            for channel in self._settings["pubchannels"]:
            
                # Initialize channel if needed
                if not channel in self._pub_channels:
                    self._pub_channels[channel] = []
                    
                # Add cargo item to channel
                self._pub_channels[channel].append(rxc)
                
                self._log.debug(str(rxc.uri) + " Sent to channel' : " + str(channel))
            

    def set(self, **kwargs):
        super().set(**kwargs)

        for key, setting in self._mqtt_settings.items():
            if key not in kwargs:
                setting = self._mqtt_settings[key]
            else:
                setting = kwargs[key]
            if key in self._settings and self._settings[key] == setting:
                continue
            elif key == 'node_format_enable':
                self._log.info("Setting %s node_format_enable: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'node_format_basetopic':
                self._log.info("Setting %s node_format_basetopic: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'nodevar_format_enable':
                self._log.info("Setting %s nodevar_format_enable: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'nodevar_format_basetopic':
                self._log.info("Setting %s nodevar_format_basetopic: %s", self.name, setting)
                self._settings[key] = setting
                continue
            elif key == 'node_JSON_enable':
                self._log.info("Setting " + self.name + " node_JSON_enable: " + setting)
                self._settings[key] = setting
                continue
            elif key == 'node_JSON_basetopic':
                self._log.info("Setting " + self.name + " node_JSON_basetopic: " + setting)
                self._settings[key] = setting
                continue
            else:
                self._log.warning("'%s' is not valid for %s: %s", setting, self.name, key)
