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
        # Initialization, first so that self._log exists for the imports below
        super().__init__(name)

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
        self.InterruptSetupError = None
        self.polling_mode = False
        try:            
            from rfm69min import Radio, InterruptSetupError
            self.Radio = Radio
            self.InterruptSetupError = InterruptSetupError
        except ModuleNotFoundError as err:      
            self._log.error(err)
            
        # sudo adduser emonhub spi

        # Watchdog variables
        self.last_received = time.monotonic()
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
        # Arm the watchdog from here, so that a radio which starts but never
        # receives anything is restarted as well as one that goes quiet
        self.last_received = time.monotonic()

        board = {'isHighPower': False, 'interruptPin': self.interruptPin, 'resetPin': self.resetPin, 'selPin':self.selPin, 'spiDevice': 0, 'encryptionKey':"89txbe4p8aik5kt3"}

        self.radio = False

        try:
            self.radio = self.Radio(self.freqBand, self.node_id, self.network_id, **board)
        except Exception as err:
            reason = str(err)
            # RPi.GPIO reports failed interrupt setup as "Failed to add edge
            # detection", other GPIO libraries word it differently, rpi-lgpio
            # raises "GPIO busy", so the exception type is checked as well
            interrupt_setup_failed = reason == "Failed to add edge detection" or (
                self.InterruptSetupError is not None and isinstance(err, self.InterruptSetupError))

            if interrupt_setup_failed:
                # == Fallback to polling mode if interrupt setup fails ==
                try:
                    self.radio = self.Radio(self.freqBand, self.node_id, self.network_id,
                                            useInterrupts=False, **board)
                except Exception as err:
                    self._log.error("Error initializing RFM69 in polling mode: "+str(err))

                if self.radio:
                    self.polling_mode = True
                    self._log.warning("Polling mode enabled for RFM69 (interrupt setup failed: "+reason+")")
                # == End of fallback to polling mode ==
            else:
                self._log.error("Error initializing RFM69 in interrupt mode: "+reason)
        
        if not self.radio or not self.radio.init_success:
            self._log.error("Could not connect to RFM69 module") 
        else:
            self._log.info("Radio setup complete")
            self.last_packet_nodeid = 0
            self.last_packet_data = []
            self.last_packet_time = 0
            # Note: __enter__ is called to set up radio resources
            self.radio.__enter__()


    def shutdown(self):
        if self.radio:
            self.radio.__exit__()

    def read(self):
        """Read data from RFM69

        """
        if self.radio and self.radio.init_success:
            # If in polling mode, manually call interrupt handler to check for packets  
            if self.polling_mode:
                self.radio._interruptHandler(self.interruptPin)

            packet = self.radio.get_packet()
            if packet:
                self._log.info("Packet received "+str(len(packet.data))+" bytes")
                # Make sure packet is a unique new packet rather than a 2nd or 3rd retry attempt
                if packet.sender==self.last_packet_nodeid and packet.data==self.last_packet_data and (time.monotonic()-self.last_packet_time)<0.5:
                    self._log.info("Discarding duplicate packet")
                    return False

                self.last_packet_nodeid = packet.sender
                self.last_packet_data = packet.data
                self.last_packet_time = time.monotonic()
                # Process packet
                c = Cargo.new_cargo(rawdata='')
                c.nodeid = packet.sender
                c.realdata = packet.data
                c.rssi = packet.RSSI

                # Set watchdog timer
                self.last_received = time.monotonic()
                return c

        # Restart the radio if nothing has been received for the watchdog
        # period, which covers a radio that failed to start as well as one
        # that has stopped receiving
        if (time.monotonic()-self.last_received) > self.watchdog_period:
            self._log.warning("No radio packets received in last "+str(self.watchdog_period)+" seconds, restarting radio")
            self.connect()

        return False

    def set(self, **kwargs):
        """

        """
        # include kwargs from parent
        super().set(**kwargs)
