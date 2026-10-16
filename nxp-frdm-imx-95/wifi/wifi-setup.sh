#!/bin/sh
# wifi-setup.sh - bring up WiFi on the FRDM i.MX95 (whinlatter BSP) and make it persistent.
#
# The BSP's wpa_supplicant is built without D-Bus, so connman cannot drive WiFi
# ("wifi is not available"). This runs wpa_supplicant directly on mlan0 plus udhcpc,
# wrapped in a systemd unit so it survives reboots. Safe to re-run; re-running with new
# credentials replaces the old network.
#
#   usage: sh wifi-setup.sh SSID [PASSPHRASE]      (omit PASSPHRASE for an open network)
#          sh wifi-setup.sh --status
#          sh wifi-setup.sh --remove

CONF=/etc/wpa_supplicant.conf
UNIT=/etc/systemd/system/wifi-mlan0.service
IFACE=mlan0

status() {
    echo "--- $IFACE ---"
    wpa_cli -i $IFACE status 2>/dev/null | grep -E '^(ssid|bssid|freq|wpa_state|ip_address)=' || echo "wpa_supplicant not running"
    ip -4 -br addr show $IFACE 2>/dev/null
    systemctl is-enabled wifi-mlan0.service 2>/dev/null | sed 's/^/unit: /'
    [ -s "$UNIT" ] || echo "unit file: MISSING/EMPTY"
    if ip -4 -o addr show $IFACE 2>/dev/null | grep -q inet; then
        if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then echo "internet: OK"; else echo "internet: FAIL (no route to 8.8.8.8)"; fi
        if timeout 8 getent hosts downloads.iotconnect.io >/dev/null 2>&1; then echo "dns: OK"; else echo "dns: FAIL"; fi
    fi
}

case "$1" in
    --status) status; exit 0 ;;
    --remove)
        systemctl disable --now wifi-mlan0.service 2>/dev/null
        rm -f "$UNIT"; systemctl daemon-reload
        pkill wpa_supplicant 2>/dev/null; pkill -f "udhcpc.*$IFACE" 2>/dev/null
        ip addr flush dev $IFACE 2>/dev/null
        echo "wifi-mlan0 removed (credentials left in $CONF)"; exit 0 ;;
    ""|-h|--help) echo "usage: $0 SSID [PASSPHRASE] | --status | --remove"; exit 1 ;;
esac

SSID=$1
PASS=$2

if [ -n "$PASS" ]; then
    L=$(printf %s "$PASS" | wc -c)
    if [ "$L" -lt 8 ] || [ "$L" -gt 63 ]; then echo "error: WPA passphrase must be 8-63 characters"; exit 1; fi
fi

# 1. credentials
{
    echo "ctrl_interface=/var/run/wpa_supplicant"
    echo "ctrl_interface_group=0"
    echo "update_config=1"
    echo
    if [ -n "$PASS" ]; then
        wpa_passphrase "$SSID" "$PASS" | grep -v '#psk'
    else
        printf 'network={\n\tssid="%s"\n\tkey_mgmt=NONE\n}\n' "$SSID"
    fi
} > "$CONF"
chmod 600 "$CONF"

# 2. systemd unit
cat > "$UNIT" <<UNITEOF
[Unit]
Description=WiFi on $IFACE (wpa_supplicant + udhcpc)
After=network.target
Wants=network.target

[Service]
Type=forking
ExecStartPre=-/usr/bin/pkill -x wpa_supplicant
ExecStartPre=-/usr/bin/pkill -f "udhcpc.*$IFACE"
ExecStartPre=/sbin/ip link set $IFACE up
ExecStart=/usr/sbin/wpa_supplicant -B -Dnl80211 -i$IFACE -c$CONF
ExecStartPost=/sbin/udhcpc -b -i $IFACE -p /run/udhcpc-$IFACE.pid -t 5 -T 3 -A 5
ExecStop=-/usr/bin/pkill -f "udhcpc.*$IFACE"
ExecStop=-/usr/bin/pkill -x wpa_supplicant
ExecStopPost=-/sbin/ip addr flush dev $IFACE

[Install]
WantedBy=multi-user.target
UNITEOF

# 3. DNS: udhcpc's hook hands the WiFi DNS server to systemd-resolved (resolvconf -> resolvectl), but the
#    BSP points /etc/resolv.conf at connman's proxy, which knows nothing about mlan0. Use resolved's stub
#    first and keep connman's proxy as fallback so Ethernet-only boards still resolve.
if [ -L /etc/resolv.conf ] || ! grep -q '127.0.0.53' /etc/resolv.conf 2>/dev/null; then
    rm -f /etc/resolv.conf
    printf 'nameserver 127.0.0.53\nnameserver 127.0.0.1\noptions timeout:2 attempts:2\n' > /etc/resolv.conf
fi

systemctl daemon-reload
systemctl enable wifi-mlan0.service >/dev/null 2>&1

# flush to eMMC BEFORE the radio comes up: ext4 delayed allocation has left zero-length unit files and a
# reverted resolv.conf behind when a board reset (marginal USB-PD supply + radio TX) or was unplugged
# seconds after setup. After this point the config survives anything.
sync
[ -s "$UNIT" ] || { echo "error: $UNIT is empty after write"; exit 3; }
[ -L /etc/resolv.conf ] && { echo "error: /etc/resolv.conf is still the connman symlink"; exit 3; }

systemctl restart wifi-mlan0.service

# 4. wait for association + lease
echo "connecting to '$SSID' ..."
i=0
while [ $i -lt 60 ]; do
    IP=$(ip -4 -o addr show $IFACE 2>/dev/null | awk '{print $4}')
    [ -n "$IP" ] && break
    sleep 1; i=$((i+1))
done

if [ -n "$IP" ]; then
    echo "WIFI OK: $SSID -> $IP"
    status
    sync
    exit 0
else
    echo "WIFI FAILED after ${i}s (no DHCP lease). Check SSID/passphrase."
    status
    exit 2
fi
