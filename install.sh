#!/bin/bash
# -------------------------------------------------------------
# emonHub install and update script
# -------------------------------------------------------------
# Assumes emonhub repository installed via git:
# git clone https://github.com/openenergymonitor/emonhub.git

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "EmonHub directory: $script_dir"

# User input: is this a raspberrypi environment that requires serial configuration
emonSD_pi_env=0
if [ -z "$1" ]; then
  read -p 'Apply raspberrypi serial configuration? (y/n): ' input
  if [ "$input" == "y" ] || [ "$input" == "Y" ]; then
    emonSD_pi_env=1
  fi
else
  emonSD_pi_env=$1
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
sudo apt-get install -y python3-serial python3-configobj python3-pip python3-pymodbus bluetooth libbluetooth-dev python3-spidev
pip3 install paho-mqtt requests py-sds011 sdm_modbus minimalmodbus

# Custom rpi-rfm69 library used for SPI RFM69 Low Power Labs interfacer
pip3 install https://github.com/openenergymonitor/rpi-rfm69/archive/refs/tags/v0.3.0-oem-4.zip

if [ "$emonSD_pi_env" = 1 ]; then

    boot_config=/boot/config.txt
    if [ -f /boot/firmware/config.txt ]; then
        boot_config=/boot/firmware/config.txt
    fi

    echo "installing or updating raspberry pi related dependencies"
    
    # Only install the GPIO library if on a Pi. Used by Pulse interfacer
    pip3 install RPi.GPIO

    # RaspberryPi Serial configuration
    # disable Pi3 Bluetooth and restore UART0/ttyAMA0 over GPIOs 14 & 15;
    # Review should this be: dtoverlay=miniuart-bt?
    echo "Disabling Bluetooth"
    sudo sed -i -n '/dtoverlay=disable-bt/!p;$a dtoverlay=disable-bt' $boot_config

    # Enable SPI
    sudo sed -i 's/#dtparam=spi=on/dtparam=spi=on/' $boot_config

    # We also need to stop the Bluetooth modem trying to use UART
    echo "Stop Bluetooth modem"
    sudo systemctl disable hciuart

    # Remove console from /boot/cmdline.txt
    echo "Remove console from /boot/cmdline.txt"
    sudo sed -i "s/console=serial0,115200 //" $boot_config

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
    sed -i "s/loglevel = DEBUG/loglevel = WARNING/" /etc/emonhub/emonhub.conf
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
# ---------------------------------------------------------
