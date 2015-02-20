import time
import paho.mqtt.client as mqtt

client = mqtt.Client()
client.connect("127.0.0.1", 1883, 60)

while True:
    topic = "emonhub/tx/30/values"
    payload = "1,1850"
    client.publish(topic, payload=payload, qos=0, retain=False)
    # client.loop()
    time.sleep(5.0)
    payload = "0,1850"
    client.publish(topic, payload=payload, qos=0, retain=False)
    # client.loop()
    time.sleep(5.0)
