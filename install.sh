#!/bin/bash
# -------------------------------------------------------------
# emonHub install and update script
# -------------------------------------------------------------
# Assumes emonhub repository installed via git:
# git clone https://github.com/openenergymonitor/emonhub.git

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "EmonHub directory: $script_dir"

# Reboot flag
reboot_required=0

# User input: is this a raspberrypi environment that requires serial configuration
emonSD_pi_env=0
if [ -z "$1" ]; then
  read -p 'Apply raspberrypi serial configuration? (y/n): ' input
  if [ "$input" == "y" ] || [ "$input" == "Y" ]; then
    emonSD_pi_env=1
  fi
else
  openenergymonitor_dir=$1
  cd $openenergymonitor_dir/EmonScripts/update
  source load_config.sh
  echo "emonSD_pi_env provided in arg = $emonSD_pi_env"
fi

# User input: check username to install emonhub with
if [ -z "$2" ]; then
  user=$USER
  read -p "Would you like to install emonhub under the $USER user? (y/n): " input
  if [ "$input" != "y" ] && [ "$input" != "Y" ]; then
    echo "Please switch to the user that you wish emonhub to be installed under"
    exit 0
  fi
  
  echo "Running apt update"
  sudo apt update
else
  user=$2
  echo "user provided as arg = $user"
fi

echo "installing or updating emonhub dependencies"
sudo apt-get install -y python3-serial python3-configobj python3-pip python3-pymodbus bluetooth python3-spidev
# removed libbluetooth-dev as this was causing a kernel update

if [ -e /usr/lib/python3.11/EXTERNALLY-MANAGED ]; then
    sudo rm -rf /usr/lib/python3.11/EXTERNALLY-MANAGED
    echo "Removed pip3 external management warning."
fi
if [ -e /usr/lib/python3.11/EXTERNALLY-MANAGED.orig ]; then
    sudo rm -rf /usr/lib/python3.11/EXTERNALLY-MANAGED.orig
    echo "Removed pip3 external management warning."
fi

# FIXME paho-mqtt V2 has new API. stick to V1.x for now
pip install --upgrade paho-mqtt==1.6.1
pip install requests py-sds011 sdm_modbus minimalmodbus

# Custom rpi-rfm69 library used for SPI RFM69 Low Power Labs interfacer
pip3 install https://github.com/openenergymonitor/rpi-rfm69/archive/refs/tags/v0.3.0-oem-4.zip

if [ "$emonSD_pi_env" = 1 ]; then

    boot_config=/boot/config.txt
    if [ -f /boot/firmware/config.txt ]; then
        boot_config=/boot/firmware/config.txt
    fi

    echo "installing or updating raspberry pi related dependencies"
    
    # Remove RPi.GPIO if it is installed, as it conflicts with rpi-lgpio
    if dpkg -l | grep -q python3-rpi.gpio; then
        echo "\nRemoving python3-rpi-gpio"
        sudo apt remove -y python3-rpi.gpio
    fi

    # Install rpi-lgpio if it is not already installed
    if ! dpkg -l | grep -q python3-rpi-lgpio; then
        echo "Installing rpi-lgpio"
        pip3 install rpi-lgpio
    fi

    # RaspberryPi Serial configuration
    # disable Pi3 Bluetooth and restore UART0/ttyAMA0 over GPIOs 14 & 15;
    # Review should this be: dtoverlay=miniuart-bt?
    echo "Disabling Bluetooth"
    sudo sed -i -n '/dtoverlay=disable-bt/!p;$a dtoverlay=disable-bt' $boot_config

    # Enable SPI
    sudo sed -i 's/#dtparam=spi=on/dtparam=spi=on/' $boot_config

    # Move CS0 to GPIO26
    # add line if not present
    if ! grep -q "^dtoverlay=spi0-cs,cs0_pin=26" $boot_config; then
        echo "dtoverlay=spi0-cs,cs0_pin=26" | sudo tee -a $boot_config
        reboot_required=1
    fi

    # We also need to stop the Bluetooth modem trying to use UART
    echo "Stop Bluetooth modem"
    sudo systemctl disable hciuart

    boot_cmdline=/boot/cmdline.txt
    if [ -f /boot/firmware/cmdline.txt ]; then
        boot_cmdline=/boot/firmware/cmdline.txt
    fi

    # Remove console from /boot/cmdline.txt
    echo "Remove console from /boot/cmdline.txt"
    sudo sed -i "s/console=serial0,115200 //" $boot_cmdline

    # stop and disable serial service??
    echo "Stop and disable serial service"
    sudo systemctl stop serial-getty@ttyAMA0.service
    sudo systemctl disable serial-getty@ttyAMA0.service
    sudo systemctl mask serial-getty@ttyAMA0.service
fi

# this should not be needed on main user but could be re-enabled
# sudo useradd -M -r -G dialout,tty -c "emonHub user" emonhub

# ---------------------------------------------------------
# EmonHub config file
# ---------------------------------------------------------
if [ ! -d /etc/emonhub ]; then
    echo "Creating /etc/emonhub directory"
    sudo mkdir /etc/emonhub
    sudo chown $user:root /var/log/emonhub
else
    echo "/etc/emonhub directory already exists"
    sudo chown $user:root /var/log/emonhub
fi

if [ ! -f /etc/emonhub/emonhub.conf ]; then
    sudo cp $script_dir/conf/emonpi2.default.emonhub.conf /etc/emonhub/emonhub.conf
    echo "No existing emonhub.conf configuration file found, installing default"
    
    # requires write permission for configuration from emoncms:config module
    sudo chmod 666 /etc/emonhub/emonhub.conf
    echo "emonhub.conf permissions adjusted to 666"

    # Temporary: replace with update to default settings file
    sudo sed -i "s/loglevel = DEBUG/loglevel = WARNING/" /etc/emonhub/emonhub.conf
    echo "Default emonhub.conf log level set to WARNING"
fi

# Fix emonhub log file permissions
if [ -d /var/log/emonhub ]; then
    echo "Setting ownership of /var/log/emonhub to $user"
    sudo chown $user:root /var/log/emonhub
fi

if [ -f /var/log/emonhub/emonhub.log ]; then
    echo "Setting ownership of /var/log/emonhub/emonhub.log to $user and permissions to 644"
    sudo chown $user:$user /var/log/emonhub/emonhub.log
    sudo chmod 644 /var/log/emonhub/emonhub.log
fi


# ---------------------------------------------------------
# Symlink emonhub source to /usr/local/bin/emonhub
# ---------------------------------------------------------
echo "Installing /usr/local/bin/emonhub symlink"
sudo ln -sf $script_dir/src /usr/local/bin/emonhub

# ---------------------------------------------------------
# Install service
# ---------------------------------------------------------
if [ -d /lib/systemd/system ]; then
  if [ ! -f /lib/systemd/system/emonhub.service ]; then
    echo "Installing emonhub.service in /lib/systemd/system (creating symlink)"
    sudo ln -sf $script_dir/service/emonhub.service /lib/systemd/system
    sudo systemctl enable emonhub.service
    sudo systemctl restart emonhub.service
  else 
    echo "emonhub.service already installed"
  fi
fi

if [ "$user" != "pi" ]; then
    echo "installing emonhub drop-in User=$user"
    if [ ! -d /lib/systemd/system/emonhub.service.d ]; then
        sudo mkdir /lib/systemd/system/emonhub.service.d
    fi
    echo $'[Service]\nUser='$user$'\nEnvironment="USER='$user'"' > emonhub.service.conf
    sudo mv emonhub.service.conf /lib/systemd/system/emonhub.service.d/emonhub.conf
fi
sudo systemctl daemon-reload
sudo systemctl restart emonhub.service

state=$(systemctl show emonhub | grep ActiveState)
echo "- Service $state"

if [ $reboot_required -eq 1 ]; then
    echo "-------------------------------------------------------------"
    echo "Reboot required to apply changes. Please reboot your system."
    echo "-------------------------------------------------------------"
fi

# ---------------------------------------------------------
