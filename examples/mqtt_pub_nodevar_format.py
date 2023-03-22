import time
import paho.mqtt.client as mqtt

client = mqtt.Client()
client.username_pw_set("emonpi", "emonpimqtt2016")
client.connect("127.0.0.1", 1883, 60)

while True:
    topic = "zigbeemqtt/temp1/temperature"
    payload = "18.5"
    client.publish(topic, payload=payload, qos=0, retain=False)
    # client.loop()
    time.sleep(5.0)
