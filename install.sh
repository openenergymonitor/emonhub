#!/bin/bash
# -------------------------------------------------------------
# emonHub install script
# -------------------------------------------------------------
# Assumes emonhub repository installed via git:
# git clone https://github.com/openenergymonitor/emonhub.git

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
usrdir=${DIR/\/emonhub/}

emonSD_pi_env=$1
if [ "$emonSD_pi_env" = "" ]; then
    read -sp 'Apply raspberrypi serial configuration? 1=yes, 0=no: ' emonSD_pi_env
    echo 
    echo "You entered $emonSD_pi_env"
    echo
fi

sudo apt-get install -y python-serial python-configobj
sudo pip install paho-mqtt requests

if [ "$emonSD_pi_env" = "1" ]; then
    # RaspberryPi Serial configuration
    # disable Pi3 Bluetooth and restore UART0/ttyAMA0 over GPIOs 14 & 15;
    # Review should this be: dtoverlay=pi3-miniuart-bt?
    sudo sed -i -n '/dtoverlay=pi3-disable-bt/!p;$a dtoverlay=pi3-disable-bt' /boot/config.txt

    # We also need to stop the Bluetooth modem trying to use UART
    sudo systemctl disable hciuart

    # Remove console from /boot/cmdline.txt
    sudo sed -i "s/console=serial0,115200 //" /boot/cmdline.txt

    # stop and disable serial service??
    sudo systemctl stop serial-getty@ttyAMA0.service
    sudo systemctl disable serial-getty@ttyAMA0.service
    sudo systemctl mask serial-getty@ttyAMA0.service
fi

cd $usrdir
if [ ! -d $usrdir/data ]; then
    mkdir data
fi

sudo useradd -M -r -G dialout,tty -c "emonHub user" emonhub

if [ ! -f $usrdir/data/emonhub.conf ]; then
    sudo cp $usrdir/emonhub/conf/emonpi.default.emonhub.conf $usrdir/data/emonhub.conf

    # Temporary: replace with update to default settings file
    sed -i "s/loglevel = DEBUG/loglevel = WARNING/" $usrdir/data/emonhub.conf
fi

# ---------------------------------------------------------
# Install service
# ---------------------------------------------------------
service=emonhub
emonhub_src_path=$usrdir/emonhub/src
emonhub_conf_path=$usrdir/data

if [ -f /lib/systemd/system/$service.service ]; then
    echo "- reinstalling $service.service"
    sudo systemctl stop $service.service
    sudo systemctl disable $service.service
    sudo rm /lib/systemd/system/$service.service
else
    echo "- installing $service.service"
fi

sudo cp $usrdir/emonhub/service/$service.service /lib/systemd/system
# Set ExecStart path to point to installed script and config location
sudo sed -i "s~ExecStart=.*~ExecStart=$emonhub_src_path/emonhub.py --config-file=$emonhub_conf_path/emonhub.conf~" /lib/systemd/system/$service.service
sudo systemctl enable $service.service
sudo systemctl restart $service.service

state=$(systemctl show $service | grep ActiveState)
echo "- Service $state"
# ---------------------------------------------------------
