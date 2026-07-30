#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# -----------------------------------------------------------------------------
# Workshop board preparation - run ONCE per board (after install.sh).
#
#   bash workshop-install.sh
#
# 1. Gives the board a UNIQUE mDNS hostname derived from its MAC address
#    (imx95-XXXX) so many boards can share a room - each is reachable at
#    http://imx95-XXXX.local:8088. Prints the URL to put on the board's card.
# 2. Installs + enables systemd services so the demo app and the claim page
#    start on every boot:  genai-app (the demo)  and  genai-provision (the
#    claim page attendees use to drop their board-kit zip).
# -----------------------------------------------------------------------------
set -e
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- 1. unique hostname from the MAC ------------------------------------------
IFACE=$(ip -o link show | awk -F': ' '$2!="lo"{print $2; exit}')
MAC=$(cat "/sys/class/net/$IFACE/address")
SUFFIX=$(echo "$MAC" | tr -d ':' | tail -c 5)   # last 4 hex chars
NAME="imx95-$SUFFIX"
echo "$NAME" > /etc/hostname
hostname "$NAME"
if ! grep -q "$NAME" /etc/hosts; then
    sed -i "s/^127.0.1.1.*/127.0.1.1 $NAME/" /etc/hosts 2>/dev/null || \
        echo "127.0.1.1 $NAME" >> /etc/hosts
fi
systemctl restart avahi-daemon 2>/dev/null || true

# --- 2. services ---------------------------------------------------------------
cat > /etc/systemd/system/genai-app.service <<EOF
[Unit]
Description=GenAI /IOTCONNECT demo app
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$DEMO_DIR
ExecStart=/usr/bin/python3 -u $DEMO_DIR/app.py
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/genai-provision.service <<EOF
[Unit]
Description=GenAI workshop claim page (board provisioning)
After=network.target

[Service]
WorkingDirectory=$DEMO_DIR
ExecStart=/usr/bin/python3 -u $DEMO_DIR/provision_server.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable genai-provision >/dev/null 2>&1
systemctl restart genai-provision
# Only auto-start the demo app when an identity is present (a claimed board);
# the claim page starts it after provisioning either way.
if [ -f "$DEMO_DIR/iotcDeviceConfig.json" ]; then
    systemctl enable genai-app >/dev/null 2>&1
    systemctl restart genai-app
else
    systemctl enable genai-app >/dev/null 2>&1
    echo "(no device identity yet - genai-app starts after the board is claimed)"
fi

echo ""
echo "=============================================================="
echo " Workshop board ready: $NAME"
echo " Claim page:  http://$NAME.local:8088"
echo " Write this URL on the board's card."
echo "=============================================================="
