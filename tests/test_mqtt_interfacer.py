"""Real Paho client and callback dispatch against a minimal loopback MQTT peer."""
import os
import socket
import select
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from interfacers.EmonHubMqttInterfacer import EmonHubMqttInterfacer


class MqttClientTest(unittest.TestCase):
    def setUp(self):
        self.peer = socket.socket()
        self.peer.bind(('127.0.0.1', 0))
        self.peer.listen(1)
        self.peer.settimeout(2)
        self.addCleanup(self.peer.close)
        self.reader = EmonHubMqttInterfacer('mqtt-test', mqtt_port=self.peer.getsockname()[1])
        self.addCleanup(self.reader._mqttc.disconnect)
        self.reader.set(pubchannels=['test-channel'])

    def receive_packet(self, connection):
        header = connection.recv(1)
        length = 0
        multiplier = 1
        while True:
            byte = connection.recv(1)[0]
            length += (byte & 127) * multiplier
            if byte < 128:
                break
            multiplier *= 128
        payload = b''
        while len(payload) < length:
            part = connection.recv(length - len(payload))
            self.assertTrue(part)
            payload += part
        return header, payload

    def read_packet(self):
        ready, _, _ = select.select([self.reader._mqttc.socket()], [], [], 2)
        self.assertTrue(ready, 'MQTT peer response did not arrive')
        self.reader._mqttc.loop_read()

    def connect(self, result=0):
        self.reader._process_post([])
        conn, _ = self.peer.accept()
        conn.settimeout(2)
        self.addCleanup(conn.close)
        header, _ = self.receive_packet(conn)
        self.assertEqual(header, b'\x10')  # CONNECT
        conn.sendall(bytes([0x20, 2, 0, result]))  # CONNACK
        self.read_packet()
        self.reader._mqttc.loop_write()
        return conn

    def test_connect_subscribe_receive_and_disconnect(self):
        conn = self.connect()
        self.assertTrue(self.reader._connected)
        header, subscribe = self.receive_packet(conn)
        self.assertEqual(header, b'\x82')
        self.assertIn(b'emonhub/tx/#', subscribe)
        conn.sendall(b'\x90\x03' + subscribe[:2] + b'\x00')  # SUBACK
        self.read_packet()
        topic = b'emonhub/tx/24/values'
        body = len(topic).to_bytes(2, 'big') + topic + b'1526,12'
        conn.sendall(bytes([0x30, len(body)]) + body)  # QoS 0 PUBLISH
        self.read_packet()
        cargo = self.reader._pub_channels['test-channel'][0]
        self.assertEqual(cargo.nodeid, 24)
        self.assertEqual(cargo.realdata, ['1526', '12'])
        conn.shutdown(socket.SHUT_RDWR)
        self.read_packet()
        self.assertFalse(self.reader._connected)

    def test_refused_connection_is_not_marked_connected(self):
        self.connect(result=5)
        self.assertFalse(self.reader._connected)


if __name__ == '__main__':
    unittest.main()
