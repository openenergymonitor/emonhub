#!/bin/bash
# -------------------------------------------------------------
# emonHub install and update script
# -------------------------------------------------------------
# Assumes emonhub repository installed via git:
# git clone https://github.com/openenergymonitor/emonhub.git
#
# This script runs on every update (called by EmonScripts
# update_component.sh) so every step checks first and only acts if
# the change is actually needed.

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "EmonHub directory: $script_dir"

# Reboot flag
reboot_required=0
# Set when something changed that requires emonhub to be restarted
restart_required=0
# Set when the service drop-in changed and a daemon-reload is needed
daemon_reload_required=0

# Custom rpi-rfm69 library used for SPI RFM69 Low Power Labs interfacer
# rfm69_version must match the VERSION file at rfm69_tag, it is used to
# detect whether the installed library is already the required version.
rfm69_tag="v0.3.0-oem-7"
rfm69_version="0.3.7"

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

# Is an apt package installed?
apt_installed() {
    dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "^install ok installed$"
}

# Cache of pip installed packages, "name==version" per line, names
# normalised to lowercase with - separators so that e.g. sdm_modbus and
# sdm-modbus compare equal. Populated by refresh_pip_list.
pip_installed=""
refresh_pip_list() {
    pip_installed=$(pip3 list --format=freeze 2>/dev/null | \
        awk -F'==' 'NF==2 {name=tolower($1); gsub(/[_.]/,"-",name); print name"=="$2}')
}

# Is a pip package installed? Argument is "name" or "name==version",
# with a version given the installed version must match exactly.
pip_has() {
    local req="$1" name want have
    name="${req%%==*}"
    want=""
    if [ "$req" != "$name" ]; then
        want="${req#*==}"
    fi
    name=$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]' | tr '_.' '--')
    have=$(printf '%s\n' "$pip_installed" | grep -m1 "^${name}==" | cut -d'=' -f3-)
    [ -n "$have" ] || return 1
    [ -z "$want" ] || [ "$have" = "$want" ] || return 1
    return 0
}

# Location of the boot configuration, moved in bookworm
boot_config=/boot/config.txt
if [ -f /boot/firmware/config.txt ]; then
    boot_config=/boot/firmware/config.txt
fi
boot_cmdline=/boot/cmdline.txt
if [ -f /boot/firmware/cmdline.txt ]; then
    boot_cmdline=/boot/firmware/cmdline.txt
fi

# Overridable for testing
device_tree_model=/proc/device-tree/model

# Is this a raspberrypi?
is_raspberrypi() {
    grep -qi "raspberry pi" $device_tree_model 2>/dev/null || \
    grep -qi "^Model.*Raspberry Pi" /proc/cpuinfo 2>/dev/null
}

# Is the rpi-lgpio package available to install?
rpi_lgpio_available() {
    apt-cache show python3-rpi-lgpio > /dev/null 2>&1
}

# The user emonhub is currently configured to run as, taken from the service
# unit and any drop-in. Empty if emonhub is not installed yet.
installed_user() {
    systemctl show emonhub.service -p User 2>/dev/null | cut -d'=' -f2-
}

# List the raspberrypi configuration steps that have not been applied yet.
# Used to decide whether there is any point asking the user, the steps
# themselves are each guarded individually so this list does not have to be
# exhaustive to be safe.
pi_config_pending=()
detect_pi_config_pending() {
    pi_config_pending=()

    if rpi_lgpio_available; then
        if apt_installed python3-rpi.gpio; then
            pi_config_pending+=("remove python3-rpi.gpio, it conflicts with rpi-lgpio")
        fi
        if ! apt_installed python3-rpi-lgpio; then
            pi_config_pending+=("install python3-rpi-lgpio")
        fi
        if ! grep -q "^dtoverlay=spi0-cs,cs0_pin=26" $boot_config 2>/dev/null; then
            pi_config_pending+=("move SPI CS0 to GPIO26 in $boot_config")
        fi
    elif ! apt_installed python3-rpi.gpio; then
        pi_config_pending+=("install python3-rpi.gpio")
    fi

    if ! grep -q "^dtoverlay=disable-bt" $boot_config 2>/dev/null; then
        pi_config_pending+=("disable bluetooth in $boot_config")
    fi
    if grep -q "^#dtparam=spi=on" $boot_config 2>/dev/null; then
        pi_config_pending+=("enable SPI in $boot_config")
    fi
    if systemctl is-enabled --quiet hciuart; then
        pi_config_pending+=("disable the hciuart bluetooth modem service")
    fi
    if grep -q "console=serial0,115200" $boot_cmdline 2>/dev/null; then
        pi_config_pending+=("remove the serial console from $boot_cmdline")
    fi
    if ! systemctl is-enabled serial-getty@ttyAMA0.service 2>/dev/null | grep -q masked; then
        pi_config_pending+=("stop and mask serial-getty@ttyAMA0.service")
    fi
}

# User input: is this a raspberrypi environment that requires serial configuration
emonSD_pi_env=0
# Run interactively (rather than from the updater), always restart at the end
interactive=0
if [ -z "$1" ]; then
    interactive=1
    if ! is_raspberrypi; then
        echo "Not a raspberrypi, skipping raspberrypi serial configuration"
    elif [ ! -f "$boot_config" ]; then
        echo "RaspberryPi detected but $boot_config not found, skipping raspberrypi serial configuration"
    else
        detect_pi_config_pending
        if [ ${#pi_config_pending[@]} -eq 0 ]; then
            echo "RaspberryPi serial configuration already applied"
            emonSD_pi_env=1
        else
            echo "RaspberryPi detected, the following has not been applied:"
            printf '  - %s\n' "${pi_config_pending[@]}"
            read -p 'Apply raspberrypi serial configuration? (y/n): ' input
            if [ "$input" == "y" ] || [ "$input" == "Y" ]; then
                emonSD_pi_env=1
            fi
        fi
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
    emonhub_user=$(installed_user)

    if [ "$emonhub_user" = "$user" ]; then
        echo "emonhub is already installed under the $user user"
    else
        if [ -n "$emonhub_user" ]; then
            echo "emonhub is currently installed under the $emonhub_user user"
            read -p "Would you like to switch emonhub to run under the $user user? (y/n): " input
        else
            read -p "Would you like to install emonhub under the $user user? (y/n): " input
        fi
        if [ "$input" != "y" ] && [ "$input" != "Y" ]; then
            echo "Please switch to the user that you wish emonhub to be installed under"
            exit 0
        fi
    fi

    echo "Running apt update"
    sudo apt update
else
    user=$2
    echo "user provided as arg = $user"
fi

# ---------------------------------------------------------
# Apt dependencies
# ---------------------------------------------------------
apt_packages="python3-serial python3-configobj python3-pip python3-pymodbus bluetooth python3-spidev"
# removed libbluetooth-dev as this was causing a kernel update

apt_missing=""
for package in $apt_packages; do
    if ! apt_installed $package; then
        apt_missing="$apt_missing $package"
    fi
done

if [ -n "$apt_missing" ]; then
    echo "- Installing emonhub apt dependencies:$apt_missing"
    sudo apt-get install -y $apt_missing
    restart_required=1
else
    echo "- Apt dependencies already installed"
fi

# ---------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------
# Remove the pip external management warning for the python version in use
python_lib_dir=$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["stdlib"])' 2>/dev/null)
for marker in "$python_lib_dir/EXTERNALLY-MANAGED" "$python_lib_dir/EXTERNALLY-MANAGED.orig"; do
    if [ -n "$python_lib_dir" ] && [ -e "$marker" ]; then
        sudo rm -rf "$marker"
        echo "- Removed pip3 external management warning: $marker"
    fi
done

# FIXME paho-mqtt V2 has new API. stick to V1.x for now
pip_packages=("paho-mqtt==1.6.1" "requests" "py-sds011" "sdm_modbus" "minimalmodbus")

refresh_pip_list
pip_missing=()
for package in "${pip_packages[@]}"; do
    if ! pip_has "$package"; then
        pip_missing+=("$package")
    fi
done

if [ ${#pip_missing[@]} -gt 0 ]; then
    echo "- Installing python dependencies: ${pip_missing[*]}"
    pip3 install --upgrade "${pip_missing[@]}"
    restart_required=1
    refresh_pip_list
else
    echo "- Python dependencies already installed"
fi

if pip_has "rpi-rfm69==$rfm69_version"; then
    echo "- rpi-rfm69 library $rfm69_version already installed"
else
    echo "- Installing rpi-rfm69 library $rfm69_tag ($rfm69_version)"
    pip3 install https://github.com/openenergymonitor/rpi-rfm69/archive/refs/tags/$rfm69_tag.zip
    restart_required=1
fi

# ---------------------------------------------------------
# RaspberryPi specific configuration
# ---------------------------------------------------------
if [ "$emonSD_pi_env" = 1 ]; then

    if [ ! -f "$boot_config" ]; then
        echo "- $boot_config not found, skipping boot configuration"
    fi

    # Migrate from RPi.GPIO to rpi-lgpio where available, RPi.GPIO must be
    # removed first as the two conflict.
    if rpi_lgpio_available; then
        if apt_installed python3-rpi.gpio; then
            echo "- Removing python3-rpi.gpio"
            sudo apt remove -y python3-rpi.gpio
            restart_required=1
        fi

        # Install rpi-lgpio if it is not already installed
        if ! apt_installed python3-rpi-lgpio; then
            echo "- Installing rpi-lgpio"
            sudo apt install -y python3-rpi-lgpio
            pip3 install rpi-lgpio
            restart_required=1
        fi

        # Move CS0 to GPIO26
        # add line if not present
        if [ -f "$boot_config" ] && ! grep -q "^dtoverlay=spi0-cs,cs0_pin=26" $boot_config; then
            echo "- Moving SPI CS0 to GPIO26"
            echo "dtoverlay=spi0-cs,cs0_pin=26" | sudo tee -a $boot_config
            reboot_required=1
        fi
    else
        echo "python3-rpi-lgpio not available, using python3-rpi.gpio instead"
        if ! apt_installed python3-rpi.gpio; then
            echo "- Installing python3-rpi.gpio"
            sudo apt install -y python3-rpi.gpio
            # Ensure RPi.GPIO is installed via pip3
            pip3 install RPi.GPIO
            restart_required=1
        fi
    fi

    # RaspberryPi Serial configuration
    # disable Pi3 Bluetooth and restore UART0/ttyAMA0 over GPIOs 14 & 15;
    # Review should this be: dtoverlay=miniuart-bt?

    if [ -f "$boot_config" ] && ! grep -q "^dtoverlay=disable-bt" $boot_config; then
        echo "- Disabling Bluetooth"
        sudo sed -i -n '/dtoverlay=disable-bt/!p;$a dtoverlay=disable-bt' $boot_config
        reboot_required=1
    fi

    # Enable SPI
    if [ -f "$boot_config" ] && grep -q "^#dtparam=spi=on" $boot_config; then
        echo "- Enabling SPI in $boot_config"
        sudo sed -i 's/#dtparam=spi=on/dtparam=spi=on/' $boot_config
        reboot_required=1
    fi

    # We also need to stop the Bluetooth modem trying to use UART
    if systemctl is-enabled --quiet hciuart; then
        echo "- Stopping Bluetooth modem"
        sudo systemctl disable hciuart
    fi

    # Remove console from cmdline.txt
    if [ -f "$boot_cmdline" ] && grep -q "console=serial0,115200" $boot_cmdline; then
        echo "- Removing serial console from $boot_cmdline"
        sudo sed -i "s/console=serial0,115200 //" $boot_cmdline
        reboot_required=1
    fi

    # Stop and disable the serial getty so that it does not hold the port
    if ! systemctl is-enabled serial-getty@ttyAMA0.service 2>/dev/null | grep -q masked; then
        echo "- Stopping and masking serial-getty@ttyAMA0.service"
        sudo systemctl stop serial-getty@ttyAMA0.service
        sudo systemctl disable serial-getty@ttyAMA0.service
        sudo systemctl mask serial-getty@ttyAMA0.service
    fi
fi

# this should not be needed on main user but could be re-enabled
# sudo useradd -M -r -G dialout,tty -c "emonHub user" emonhub

# ---------------------------------------------------------
# EmonHub config file
# ---------------------------------------------------------
if [ ! -d /etc/emonhub ]; then
    echo "Creating /etc/emonhub directory"
    sudo mkdir /etc/emonhub
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
    restart_required=1
fi

# Fix emonhub log file permissions
if [ -d /var/log/emonhub ] && [ "$(stat -c '%U:%G' /var/log/emonhub)" != "$user:root" ]; then
    echo "Setting ownership of /var/log/emonhub to $user:root"
    sudo chown $user:root /var/log/emonhub
fi

if [ -f /var/log/emonhub/emonhub.log ] && \
   [ "$(stat -c '%U:%G:%a' /var/log/emonhub/emonhub.log)" != "$user:$user:644" ]; then
    echo "Setting ownership of /var/log/emonhub/emonhub.log to $user and permissions to 644"
    sudo chown $user:$user /var/log/emonhub/emonhub.log
    sudo chmod 644 /var/log/emonhub/emonhub.log
fi

# ---------------------------------------------------------
# Symlink emonhub source to /usr/local/bin/emonhub
# ---------------------------------------------------------
# -n so that an existing symlink is replaced rather than followed
if [ "$(readlink /usr/local/bin/emonhub)" != "$script_dir/src" ]; then
    echo "Installing /usr/local/bin/emonhub symlink"
    sudo ln -sfn $script_dir/src /usr/local/bin/emonhub
    restart_required=1
fi

# ---------------------------------------------------------
# Install service
# ---------------------------------------------------------
if [ -d /lib/systemd/system ]; then

    # LogsDirectory/RuntimeDirectory require systemd >= 235 (Debian Buster / Ubuntu 18.04+)
    systemd_version=$(systemctl --version | awk 'NR==1{print $2}')
    if [ "$systemd_version" -ge 235 ] 2>/dev/null; then
        service_file=$script_dir/service/emonhub.service.modern
    else
        service_file=$script_dir/service/emonhub.service
    fi

    installed_service=$(readlink /lib/systemd/system/emonhub.service)

    if [ -f /lib/systemd/system/emonhub.service ] && [ -z "$installed_service" ]; then
        # Not a symlink, installed by hand or by an older install script, leave alone
        echo "emonhub.service already installed (not managed by this script)"
    elif [ "$installed_service" != "$service_file" ]; then
        echo "Installing $(basename $service_file) in /lib/systemd/system (systemd $systemd_version)"
        sudo ln -sfn $service_file /lib/systemd/system/emonhub.service
        # reload now so that the is-enabled check below sees the new unit
        sudo systemctl daemon-reload
        restart_required=1
    else
        echo "emonhub.service already installed"
    fi

    if ! systemctl is-enabled --quiet emonhub.service; then
        echo "Enabling emonhub.service"
        sudo systemctl enable emonhub.service
    fi
fi

dropin_dir=/lib/systemd/system/emonhub.service.d
dropin=$dropin_dir/emonhub.conf

if [ "$user" != "pi" ]; then
    dropin_content=$'[Service]\nUser='$user$'\nEnvironment="USER='$user'"'

    if [ ! -f "$dropin" ] || [ "$(cat $dropin)" != "$dropin_content" ]; then
        echo "installing emonhub drop-in User=$user"
        if [ ! -d "$dropin_dir" ]; then
            sudo mkdir $dropin_dir
        fi
        tmp_dropin=$(mktemp)
        echo "$dropin_content" > $tmp_dropin
        sudo install -m 644 -o root -g root $tmp_dropin $dropin
        rm -f $tmp_dropin
        daemon_reload_required=1
        restart_required=1
    else
        echo "emonhub drop-in User=$user already installed"
    fi
elif [ -f "$dropin" ]; then
    # pi is the user set in the service unit itself, remove any drop-in left
    # over from a previous install under a different user
    echo "removing emonhub drop-in, running as the default pi user"
    sudo rm -f $dropin
    sudo rmdir --ignore-fail-on-non-empty $dropin_dir
    daemon_reload_required=1
    restart_required=1
fi

if [ $daemon_reload_required -eq 1 ]; then
    sudo systemctl daemon-reload
fi

# ---------------------------------------------------------
# Restart emonhub only if needed
# ---------------------------------------------------------
# Restarting emonhub loses any data buffered in memory by the interfacers,
# so only restart if something has actually changed. Run interactively or
# with EMONHUB_FORCE_RESTART=1 to always restart.

if [ "$interactive" = 1 ] || [ "$EMONHUB_FORCE_RESTART" = "1" ]; then
    restart_required=1
elif ! systemctl is-active --quiet emonhub.service; then
    echo "- emonhub service is not running"
    restart_required=1
elif [ $restart_required -eq 0 ]; then
    # Restart if any source file has been modified since the service started.
    # The service start time is calculated from the monotonic timestamp to
    # avoid timezone parsing, with a small margin so that we err on the side
    # of restarting. __pycache__ is ignored as it is written by emonhub itself.
    started_mono=$(systemctl show emonhub.service -p ActiveEnterTimestampMonotonic | cut -d'=' -f2)
    started_epoch=$(awk -v now="$(date +%s)" -v uptime="$(cut -d' ' -f1 /proc/uptime)" \
        -v mono="$started_mono" \
        'BEGIN { if (mono == "" || mono+0 == 0) print 0; else printf "%d", now - uptime + mono/1000000 - 10 }')

    if [ -n "$(find $script_dir/src \( -name '__pycache__' -o -name '*.pyc' \) -prune \
               -o -type f -newermt "@$started_epoch" -print -quit 2>/dev/null)" ]; then
        echo "- emonhub source updated since service started"
        restart_required=1
    fi
fi

if [ $restart_required -eq 1 ]; then
    echo "Restarting emonhub service"
    sudo systemctl restart emonhub.service
else
    echo "No changes, emonhub service restart not required"
fi

state=$(systemctl show emonhub | grep ActiveState)
echo "- Service $state"

if [ $reboot_required -eq 1 ]; then
    echo "-------------------------------------------------------------"
    echo "Reboot required to apply changes. Please reboot your system."
    echo "-------------------------------------------------------------"

    # create file /tmp/emon_reboot_required
    if [ ! -f /tmp/emon_reboot_required ]; then
        echo "Reboot required" > /tmp/emon_reboot_required
    fi
fi

# ---------------------------------------------------------
