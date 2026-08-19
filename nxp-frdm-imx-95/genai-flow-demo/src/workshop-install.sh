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
# 2. Installs + enables systemd services so the demo stack starts on every
#    boot:  genai-app (the demo),  genai-provision (the claim page attendees
#    use to drop their board-kit zip),  genai-camera (HTTPS camera/responses
#    server on :8080)  and  genai-bench (the model-shootout UI on :8090).
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
# Only run once the board is claimed. Without an identity the app can't connect,
# so on an unclaimed board systemd would auto-start it, fail, and (Restart=on-failure)
# retry-loop forever. This condition makes systemd skip it cleanly until the claim
# writes the identity; provision_server's 'systemctl restart genai-app' on claim
# re-checks the condition and starts it.
ConditionPathExists=$DEMO_DIR/iotcDeviceConfig.json

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

cat > /etc/systemd/system/genai-camera.service <<EOF
[Unit]
Description=GenAI demo camera/responses web server
After=network.target

[Service]
WorkingDirectory=$DEMO_DIR
ExecStart=/usr/bin/python3 -u $DEMO_DIR/camera-server.py
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/genai-bench.service <<EOF
[Unit]
Description=GenAI LLM shootout web UI
After=network.target

[Service]
WorkingDirectory=$DEMO_DIR
ExecStart=/usr/bin/python3 -u $DEMO_DIR/bench_server.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable genai-provision genai-camera genai-bench >/dev/null 2>&1
systemctl restart genai-provision genai-camera genai-bench
# Only auto-start the demo app when an identity is present (a claimed board);
# the claim page starts it after provisioning either way.
if [ -f "$DEMO_DIR/iotcDeviceConfig.json" ]; then
    systemctl enable genai-app >/dev/null 2>&1
    systemctl restart genai-app
else
    systemctl enable genai-app >/dev/null 2>&1
    echo "(no device identity yet - genai-app starts after the board is claimed)"
fi

# --- 3. readiness checks -------------------------------------------------------
LLAMA_DIR=$(python3 -c "import json;print(json.load(open('$DEMO_DIR/genai-config.json')).get('llama_dir','/opt/llama'))" 2>/dev/null || echo /opt/llama)
WARN=""
[ -d /root/eiq_genai_flow ] || WARN="$WARN\n  ! eIQ GenAI Flow is not installed - ask-llm, voice and RAG will not work (README section 3)"
[ -x "$LLAMA_DIR/src/build/bin/llama-cli" ] || WARN="$WARN\n  ! llama.cpp is not installed at $LLAMA_DIR - GGUF models pushed from /IOTCONNECT cannot run.\n    Copy it from a prepared board:  scp -r root@<ready-board>:$LLAMA_DIR/src/build $LLAMA_DIR/src/"

echo ""
echo "=============================================================="
echo " Workshop board ready: $NAME"
echo " Claim page:  http://$NAME.local:8088"
echo " Shootout:    http://$NAME.local:8090"
echo " Camera:      https://$NAME.local:8080/live   (accept the self-signed cert once)"
echo " Write the claim URL on the board's card."
if [ -n "$WARN" ]; then
    echo "--------------------------------------------------------------"
    printf " Before the workshop:%b\n" "$WARN"
fi
echo "=============================================================="
