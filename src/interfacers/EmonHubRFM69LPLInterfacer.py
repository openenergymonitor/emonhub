
from emonhub_interfacer import EmonHubInterfacer
import Cargo
import time

"""class EmonHubRFM69LPLInterfacer

Read RFM69 radio data (LowPowerLabs format)

"""
class EmonHubRFM69LPLInterfacer(EmonHubInterfacer):

    def __init__(self, name, nodeid = 5, networkID = 210, interruptPin = 22, resetPin = None, selPin = 26, freqBand = 43):
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
            GPIO.setwarnings(False)
        except ModuleNotFoundError as err:      
            self._log.error(err)

        self.Radio = False
        try:            
            from RFM69 import Radio
            self.Radio = Radio
        except ModuleNotFoundError as err:      
            self._log.error(err)
            
        # sudo adduser emonhub spi

        # Initialization
        super().__init__(name)

        # Watchdog variables
        self.last_received = False
        self.watchdog_period = 300
        
        self.node_id = int(nodeid)
        self.network_id = int(networkID)
        self.interruptPin = int(interruptPin)
        self.selPin = int(selPin)
        self.freqBand = int(freqBand)
        
        if resetPin != None and resetPin != 'None':
            resetPin = int(resetPin)
        else:
            resetPin = None

        self.resetPin = resetPin
        
        self._log.info("Creating RFM69 LowPowerLabs interfacer")
        self._log.info("RFM69 node_id = "+str(self.node_id))
        self._log.info("RFM69 network_id = "+str(self.network_id))  
        self._log.info("RFM69 interruptPin = "+str(self.interruptPin))
        self._log.info("RFM69 resetPin = "+str(self.resetPin))
        self._log.info("RFM69 selPin = "+str(self.selPin))
        
        self._log.info("Starting radio setup")
        self.connect()

    def connect(self):
        """Connect to RFM69

        """
        self._log.info("Connecting to RFM69")
        self.last_received = False

        board = {'isHighPower': False, 'interruptPin': self.interruptPin, 'resetPin': self.resetPin, 'selPin':self.selPin, 'spiDevice': 0, 'encryptionKey':"89txbe4p8aik5kt3"}
        self.radio = self.Radio(self.freqBand, self.node_id, self.network_id, verbose=False, **board)
        
        if not self.radio.init_success:
            self._log.error("Could not connect to RFM69 module") 
        else:
            self._log.info("Radio setup complete")
            self.last_packet_nodeid = 0
            self.last_packet_data = []
            self.last_packet_time = 0
            self.radio.__enter__()


    def shutdown(self):
        self.radio.__exit__()
        pass

    def read(self):
        """Read data from RFM69

        """
        if not self.radio.init_success:
            return False
            
        packet = self.radio.get_packet()
        if packet:
            self._log.info("Packet received "+str(len(packet.data))+" bytes")
            # Make sure packet is a unique new packet rather than a 2nd or 3rd retry attempt
            if packet.sender==self.last_packet_nodeid and packet.data==self.last_packet_data and (time.time()-self.last_packet_time)<0.5:
                self._log.info("Discarding duplicate packet")
                return False

            self.last_packet_nodeid = packet.sender
            self.last_packet_data = packet.data
            self.last_packet_time = time.time()
            # Process packet
            c = Cargo.new_cargo(rawdata='')
            c.nodeid = packet.sender
            c.realdata = packet.data
            c.rssi = packet.RSSI

            # Set watchdog timer
            self.last_received = time.time()
            return c

        if self.last_received and (time.time()-self.last_received) > self.watchdog_period:
            self._log.warning("No radio packets received in last "+str(self.watchdog_period)+" seconds, restarting radio")
            self.connect()

        return False

    def set(self, **kwargs):
        """

        """
        # include kwargs from parent
        super().set(**kwargs)
