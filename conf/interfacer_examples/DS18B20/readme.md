### Direct DS18B20 temperature sensing

This EmonHub interfacer can be used to read directly from DS18B20 temperature sensors connected to the GPIO pins on the RaspberryPi. At present a couple of manual setup steps are required to enable DS18B20 temperature sensing before using this EmonHub interfacer.

**Manual RaspberryPi configuration:**

1\. SSH into your RaspberryPi, open /boot/config.txt in an editor:

    sudo nano /boot/config.txt

2\. Add the following to the end of the file:

    dtoverlay=w1-gpio

3\. Exit and reboot the Pi

    sudo reboot
    
4\. SSH back in again and run the following to enable the required modules:

    sudo modprobe w1-gpio
    sudo modprobe w1-therm

**Configuring the Interfacer:**

Login to the local copy of Emoncms running on the emonPi/emonBase and navigate to Setup > EmonHub. Click on 'Edit Config' and add the following config in the interfacers section to enable reading from the temperature sensors.

- **read_interval:** Interval between readings in seconds. 
- **ids:** This can be used to link specific sensors addresses to input names listed under the names property. 
- **names:** Names associated with sensor id's, ordered by index.

Example DS18B20 EmonHub configuration:

    [[DS18B20]]
        Type = EmonHubDS18B20Interfacer
        [[[init_settings]]]
        [[[runtimesettings]]]
            pubchannels = ToEmonCMS,
            read_interval = 10
            nodename = sensors
            # ids = 28-000008e2db06, 28-000009770529, 28-0000096a49b4
            # names = ambient, cyl_bot, cyl_top

