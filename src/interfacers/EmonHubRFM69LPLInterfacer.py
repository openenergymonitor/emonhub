
from emonhub_interfacer import EmonHubInterfacer
import Cargo
import time

"""class EmonHubRFM69LPLInterfacer

Read RFM69 radio data (LowPowerLabs format)

"""
class EmonHubRFM69LPLInterfacer(EmonHubInterfacer):

    def __init__(self, name, nodeid, networkID):
        """Initialize Interfacer

        nodeid (integer): radio nodeid 1-1023
        networkID (integer): radio networkID 0-255

        """
        try:
            import spidev
        except ModuleNotFoundError as err:
            self._log.error(err)

        try:            
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
        except ModuleNotFoundError as err:      
            self._log.error(err)

        try:            
            from RFM69 import Radio
        except ModuleNotFoundError as err:      
            self._log.error(err)
            
        # sudo adduser emonhub spi

        # Initialization
        super().__init__(name)
        
        node_id = int(nodeid)
        network_id = int(networkID)
        
        self._log.info("Creating RFM69 LowPowerLabs interfacer")
        self._log.info("node_id = "+str(node_id))
        self._log.info("network_id = "+str(network_id))  
            
        self._log.info("Starting radio setup")
        
        board = {'isHighPower': False, 'interruptPin': 22, 'resetPin': None, 'spiDevice': 0, 'encryptionKey':"89txbe4p8aik5kt3"}
        self.radio = Radio(43, node_id, network_id, verbose=False, **board) 

        self._log.info("Radio setup complete")
        
        self.last_packet_nodeid = 0;
        self.last_packet_data = []
        
        self.radio.__enter__()

    def shutdown(self):
        self.radio.__exit__()
        pass

    def read(self):
        """Read data from RFM69

        """
        packet = self.radio.get_packet()
        if packet:
            self._log.info("Packet received "+str(len(packet.data))+" bytes")
            
            # Make sure packet is a unique new packet rather than a 2nd or 3rd retry attempt
            #if packet.sender != self.last_packet_nodeid or packet.data != self.last_packet_data:
            #    self.last_packet_nodeid = packet.sender
            #    self.last_packet_data = packet.data
                
            # Process packet
            c = Cargo.new_cargo(rawdata='')
            c.nodeid = packet.sender
            c.realdata = packet.data
            c.rssi = packet.RSSI
            return c
        

    def set(self, **kwargs):
        """

        """
        # include kwargs from parent
        super().set(**kwargs)
