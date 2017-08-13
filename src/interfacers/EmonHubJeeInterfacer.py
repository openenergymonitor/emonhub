import time
from pydispatch import dispatcher

import datetime
import Cargo
import EmonHubSerialInterfacer as ehi
import urllib
import struct
import json

"""class EmonHubJeeInterfacer

Monitors the serial port for data from "Jee" type device

"""

class EmonHubJeeInterfacer(ehi.EmonHubSerialInterfacer):

    def __init__(self, name, com_port='/dev/ttyAMA0', com_baud=0):
        """Initialize Interfacer

        com_port (string): path to COM port

        """

        # Initialization
        if com_baud != 0:
            super(EmonHubJeeInterfacer, self).__init__(name, com_port, com_baud)
        else:
            super(EmonHubJeeInterfacer, self).__init__(name, com_port, 38400)
        
        # Display device firmware version and current settings
        self.info = ["",""]
        if self._ser is not None:
            self._ser.write("v")
            time.sleep(2)
            self._rx_buf = self._rx_buf + self._ser.readline()
            if '\r\n' in self._rx_buf:
                self._rx_buf=""
                info = self._rx_buf + self._ser.readline()[:-2]
                if info != "":
                    # Split the returned "info" string into firmware version & current settings
                    self.info[0] = info.strip().split(' ')[0]
                    self.info[1] = info.replace(str(self.info[0]), "")
                    self._log.info( self.name + " device firmware version: " + self.info[0])
                    self._log.info( self.name + " device current settings: " + str(self.info[1]))
                else:
                    # since "v" command only v11> recommend firmware update ?
                    #self._log.info( self.name + " device firmware is pre-version RFM12demo.11")
                    self._log.info( self.name + " device firmware version & configuration: not available")
            else:
                self._log.warning("Device communication error - check settings")
        self._rx_buf=""
        self._ser.flushInput()

        # Initialize settings
        self._defaults.update({'pause': 'off', 'interval': 0, 'datacode': 'h'})

        # This line will stop the default values printing to logfile at start-up
        # unless they have been overwritten by emonhub.conf entries
        # comment out if diagnosing a startup value issue
        self._settings.update(self._defaults)

        # Jee specific settings to be picked up as changes not defaults to initialise "Jee" device
        self._jee_settings =  ({'baseid': '15', 'frequency': '433', 'group': '210', 'quiet': 'True', 'calibration': '230V' 
		, 'feedbroadcastinterval': 0
		, 'feedreadonlyapikey': ''
		, 'feedurl':'http://localhost/emoncms/feed/fetch.json'
		, 'feedlisturl':'http://localhost/emoncms/feed/list.json'
		, 'feedlist':'0' })
        self._jee_prefix = ({'baseid': 'i', 'frequency': '', 'group': 'g', 'quiet': 'q', 'calibration': 'p' 
		,'feedbroadcastinterval':'' 
		,'feedreadonlyapikey': '' 
		,'feedurl':'' 
		,'feedlisturl':'' 
		,'feedlist':''})

	# Set default
	self._interval_timestamp = 0
	self._feed_interval_timestamp = 0

        # Pre-load Jee settings only if info string available for checks
        if all(i in self.info[1] for i in (" i", " g", " @ ", " MHz")):
            self._settings.update(self._jee_settings)


    def read(self):
        """Read data from serial port and process if complete line received.

        Return data as a list: [NodeID, val1, val2]

        """

        # Read serial RX
        self._rx_buf = self._rx_buf + self._ser.readline()

        # If line incomplete, exit
        if '\r\n' not in self._rx_buf:
            return

        # Remove CR,LF.
        f = self._rx_buf[:-2].strip()

        # Reset buffer
        self._rx_buf = ''

        if not f:
            return

        if f[0] == '\x01':
            #self._log.debug("Ignoring frame consisting of SOH character" + str(f))
            return

        if f[0] == '?':
            self._log.debug("Discarding RX frame 'unreliable content'" + str(f))
            return False

        # Discard information messages
        if '>' in f:
            if '->' in f:
                self._log.debug("confirmed sent packet size: " + str(f))
                return
            self._log.debug("acknowledged command: " + str(f))
            return

        # Record current device settings
        if " i" and " g" and " @ " and " MHz" in f:
            self.info[1] = f
            self._log.debug("device settings updated: " + str(self.info[1]))
            return

        # Save raw packet to new cargo object
        c = Cargo.new_cargo(rawdata=f)

        # Convert single string to list of string values
        f = f.split(' ')

        # Strip leading 'OK' from frame if needed
        if f[0]=='OK':
            f = f[1:]
 
        # Extract RSSI value if it's available
        if str(f[-1])[0]=='(' and str(f[-1])[-1]==')':
            r = f[-1][1:-1]
            try:
                c.rssi = int(r)
            except ValueError:
                self._log.warning("Packet discarded as the RSSI format is invalid: "+ str(f))
                return
            f = f[:-1]

        try:
            # Extract node id from frame
            c.nodeid = int(f[0]) + int(self._settings['nodeoffset'])
        except ValueError:
            return

        try:
            # Store data as a list of integer values
            c.realdata = [int(i) for i in f[1:]]
        except ValueError:
            return

        return c

    def set(self, **kwargs):
        """Send configuration parameters to the "Jee" type device through COM port

        **kwargs (dict): settings to be modified. Available settings are
        'baseid', 'frequency', 'group'. Example:
        {'baseid': '15', 'frequency': '4', 'group': '210'}
	emonNotify settings also passed into this function
        
        """

        for key, setting in self._jee_settings.iteritems():

	    command = ''
            # Decide which setting value to use
            if key in kwargs.keys():
                setting = kwargs[key]
            else:
                setting = self._jee_settings[key]

            # convert bools to ints
            if str.capitalize(str(setting)) in ['True', 'False']:
                setting = int(setting == "True")

            # confirmation string always contains baseid, group anf freq
            if " i" and " g" and " @ " and " MHz" in self.info[1]:
                # If setting confirmed as already set, continue without changing
                if (self._jee_prefix[key] + str(setting)) in self.info[1].split():
                    continue
            elif key in self._settings and self._settings[key] == setting:
                continue
            if key == 'baseid' and int(setting) >=1 and int(setting) <=26:
                command = str(setting) + 'i'
            elif key == 'frequency' and setting in ['433','868','915']:
                command = setting[:1] + 'b'
            elif key == 'group'and int(setting) >=0 and int(setting) <=250:
                command = str(setting) + 'g'
            elif key == 'quiet' and int(setting) >=0 and int(setting) <2:
                command = str(setting) + 'q'
            elif key == 'calibration' and setting == '230V':
                command = '1p'
            elif key == 'calibration' and setting == '110V':
                command = '2p'
	    #Settings for emonNOTIFY dont get sent to JEELIB module
            elif key == 'feedbroadcastinterval' and str(setting).isdigit() and int(setting)>0:
		setting = int(setting)
	    elif (key in ['feedreadonlyapikey','feedlist','feedurl','feedlisturl','feedreadonlyapikey']):
		command = ''
            else:
                self._log.warning("In interfacer set '%s' is not a valid setting for %s: %s" % (str(setting), self.name, key))
                continue

            self._settings[key] = setting
	    #self._log.info("%s config setting '%s': '%s'" % (self.name, key, setting))
	    if (command!=''):
		#Send to JEELIB Arduino on COM port
                self._log.info("JEELIB setting %s  %s: %s" % (self.name, key, setting) + " (" + command + ")")
                self._ser.write(command)
                # Wait a sec between two settings
                time.sleep(1)

        # include kwargs from parent
        super(EmonHubJeeInterfacer, self).set(**kwargs)

	self.resetEmonNotifyLabelList()

	#self._log.debug("feedbroadcastinterval=%s feedreadonlyapikey=%s feedlist=%s" % ( self._settings['feedbroadcastinterval'],  self._settings['feedreadonlyapikey'], self._settings['feedlist']))

    def resetEmonNotifyLabelList(self):
	"""Reset the emonNotify feed settings and also re-transmit the labels"""
	#Clone the list
	self._exported_feeds=list(self._settings['feedlist'])
        self._exported_sequence=1

    def emoncmsfeedvalues(self,url,api,feedid):
	"""read multiple feed values from EMONCMS parse the JSON reply into Python array
	"""
       
	data_url=str(url)+"?apikey=" + str(api) + "&ids=" + str(feedid)
        try:
                sock = urllib.urlopen(data_url)
                data_str = sock.read()
                sock.close
                return json.loads(data_str)
        except Exception, detail:
                self._log.debug(detail)

    def emoncmsfeednames(self,url,api):
	"""read all feeds from EMONCMS parse the JSON reply into Python array
        """

        data_url=str(url)+"?apikey=" + str(api)
        try:
                sock = urllib.urlopen(data_url)
                data_str = sock.read()
                sock.close
                return json.loads(data_str)
        except Exception, detail:
                self._log.debug(detail)



    def action(self):
        """Actions that need to be done on a regular basis. 
        
        This should be called in main loop by instantiater.
        
        """

        t = time.time()

        # Broadcast time to synchronize emonGLCD
        interval = int(self._settings['interval'])
        if interval:  # A value of 0 means don't do anything
            if (t - self._interval_timestamp) > interval:
                self._interval_timestamp = t
                now = datetime.datetime.now();
                self._log.debug(self.name + " broadcasting time: %02d:%02d" % (now.hour, now.minute))
                self._ser.write("00,%02d,%02d,00,s" % (now.hour, now.minute))


	feedbroadcastinterval = int(self._settings['feedbroadcastinterval'])
	if (feedbroadcastinterval>0 and self._settings['feedreadonlyapikey']!=""):
		if (t - self._feed_interval_timestamp) > feedbroadcastinterval:
			self._feed_interval_timestamp = t

			self._log.debug(self.name + " transmitting feed values over RFM")

			try:
				output=""

				#emonNOTIFY screen 0 (0-15 allowed)
				#Message type = 0 (reading/values)
				headerbyte=(0 & 0x0F)<<4 | (0 & 0x0F)

				output+="%02d," % (headerbyte)

				#Spit out the current time EPOC as 4 bytes
				#Note this only returns UTC based date/time values
				now = datetime.datetime.now()
				stamp = time.mktime(now.timetuple())
				for b in bytearray( struct.pack('<L', stamp)  ):
					output+="%02d," % (b)

				feed_ids=",".join(map(str, self._settings['feedlist']))
				feed_values=self.emoncmsfeedvalues(self._settings['feedurl'], 
					self._settings['feedreadonlyapikey'], 
					feed_ids)

				for value in feed_values:
					# Remove any floating point from the raw value by multiply by 100
					v = int(float(value) * 100);
					# Pack as little-endian signed long - 4 bytes
					barray = bytearray(struct.pack("<l", v))
					for b in barray:
						output+="%02d," % (b)

				#Specify the receiver of our message
				output+="04s"
				self._ser.write(output)
				#self._log.debug(output)

				# Now try and send feed text labels to emonNOTIFY
				self.emonnotify_labels()

		        except Exception, detail:
	                	self._log.debug(detail)

    def emonnotify_labels(self):
	"""Send feed name labels and units of energy remotely to emonNotify via RFM module
	"""
	#We only transmit a single label on each loop to prevent swamping the RFM module
	#and the radio bandwidth and we only transmit the labels once when emonHUB starts up
	#and again if the configuration changes
	if len(self._exported_feeds) > 0:
		feed_list=self.emoncmsfeednames(self._settings['feedlisturl'], self._settings['feedreadonlyapikey'])

		first_in_list = self._exported_feeds[0]

                for feed in feed_list:
                	if str(feed["id"]) in first_in_list:
                                output=""
                                # Message type = 1 feed label
                                headerbyte=(0 & 0x0F)<<4 | (1 & 0x0F)
                                output+="%02d," % (headerbyte)
                                output+="%02d," % (self._exported_sequence)
                                #Label (max 14 chars)
                                label=feed["name"][:14]

                                barray = bytearray(label.encode())
                                for b in barray:
                                	output+="%02d," % (b)

                                # Trailing zero byte to terminate string
                                output+="00,"

				units=self.feed_name_to_energy_unit(feed["name"])[:5]
				barray = bytearray(units.encode())
                                for b in barray:
                                        output+="%02d," % (b)

				output+="00,"

                                output+="04s"
				# Wait 2 seconds before transmission to ensure previous feed data message has got there
				time.sleep(2)
                                self._ser.write(output)

				self._log.debug("Sending label '%s' and units '%s' sequence %i" %( label, units, self._exported_sequence ))

				self._exported_sequence=self._exported_sequence+1
                                self._exported_feeds.remove(first_in_list)
				break


    def feed_name_to_energy_unit(self,argument):
	"""Maps commonly used feed names into its unit of energy ideally this would be read from a database contained in emonCMS"""
	switcher= {
        	'use': "watts",
        	'use_kwh': "kW/h",
		'solar': "watts",
		'import': "watts",
		'solar_kwh': "kW/h",
		'export': "watts",
		'bmwi3-fuelPercent':'%',
		'bmwi3-mileage':'miles',
		'bmwi3-beRemainingRangeElectricMile':'miles',
		'bmwi3-chargingLevelHv':'% Bat'
	}
	return switcher.get(argument, "")
