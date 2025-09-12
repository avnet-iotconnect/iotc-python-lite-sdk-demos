# Optional Wi-Fi Setup Guide

## Introduction

This simple guide will help you connect your board to a wireless network instead of having to use an ethernet
connection.

## Guide

There is no hardware setup required, all configuration will be done in the terminal of your board.

**If this is not the first time** you have connected this device to a Wi-Fi network, execute these commands to stop the
existing Wi-Fi service:

```
systemctl stop wpa_supplicant@wlan0.service
systemctl disable wpa_supplicant@wlan0.service
rm -r /etc/wpa_supplicant
```

After you have run those commands (or if this is the first time you're connecting the device to a wireless network), run
these commands:

```
ifconfig wlan0 up
echo "[Match]" > /lib/systemd/network/51-wireless.network
echo "Name=wlan0" >> /lib/systemd/network/51-wireless.network
echo "[Network]" >> /lib/systemd/network/51-wireless.network
echo "DHCP=ipv4" >> /lib/systemd/network/51-wireless.network
mkdir -p /etc/wpa_supplicant/
echo "ctrl_interface=/var/run/wpa_supplicant" > /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
echo "eapol_version=1" >> /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
echo "ap_scan=1" >> /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
echo "fast_reauth=1" >> /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
echo "" >> /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
```

Next it is time to enter your network's credentials. Execute this command, but with your network SSID and password (
exclude parentheses):

```
wpa_passphrase (ssid) (password) >> /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
```

For example, if your network SSID is "HomeNetwork" and the password is "ABC123!" then your command would be:

```
wpa_passphrase HomeNetwork ABC123! >> /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
```

Finally, run these commands to finish the wi-fi setup process:

```
systemctl enable wpa_supplicant@wlan0.service
systemctl restart systemd-networkd.service
systemctl restart wpa_supplicant@wlan0.service
```

Your device should now be connected to your wi-fi network, and should re-connect automatically after future reboots.
