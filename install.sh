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
fi

# User input: check username to install emonhub with
user=$USER
if [ -z "$2" ]; then
  read -p "Would you like to install emonhub under the $USER user? (y/n): " input
  if [ "$input" != "y" ] && [ "$input" != "Y" ]; then
    echo "Please switch to the user that you wish emonhub to be installed under"
    exit 0
  fi
  
  echo "Running apt update"
  sudo apt update
fi

sudo apt-get install -y python3-serial python3-configobj python3-pip python3-pymodbus bluetooth libbluetooth-dev
pip3 install paho-mqtt requests pybluez py-sds011 sdm_modbus minimalmodbus

if [ "$emonSD_pi_env" = 1 ]; then

    # Only install the GPIO library if on a Pi. Used by Pulse interfacer
    pip3 install RPi.GPIO

    # RaspberryPi Serial configuration
    # disable Pi3 Bluetooth and restore UART0/ttyAMA0 over GPIOs 14 & 15;
    # Review should this be: dtoverlay=miniuart-bt?
    sudo sed -i -n '/dtoverlay=disable-bt/!p;$a dtoverlay=disable-bt' /boot/config.txt

    # We also need to stop the Bluetooth modem trying to use UART
    sudo systemctl disable hciuart

    # Remove console from /boot/cmdline.txt
    sudo sed -i "s/console=serial0,115200 //" /boot/cmdline.txt

    # stop and disable serial service??
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
    sudo mkdir /etc/emonhub
fi

if [ ! -f /etc/emonhub/emonhub.conf ]; then
    sudo cp $script_dir/conf/emonpi.default.emonhub.conf /etc/emonhub/emonhub.conf
    
    # requires write permission for configuration from emoncms:config module
    sudo chmod 666 /etc/emonhub/emonhub.conf

    # Temporary: replace with update to default settings file
    sed -i "s/loglevel = DEBUG/loglevel = WARNING/" /etc/emonhub/emonhub.conf
fi

# ---------------------------------------------------------
# Symlink emonhub source to /usr/local/bin/emonhub
# ---------------------------------------------------------
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
    echo $'[Service]\nEnvironment="USER='$user'"' > emonhub.service.conf
    sudo mv emonhub.service.conf /lib/systemd/system/emonhub.service.d/emonhub.conf
fi
sudo systemctl daemon-reload
sudo systemctl restart emonhub.service

state=$(systemctl show emonhub | grep ActiveState)
echo "- Service $state"
# ---------------------------------------------------------
