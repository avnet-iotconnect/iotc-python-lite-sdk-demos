#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
#
# Install / update the RZ/G3E vision demo in the directory this script lives in
# (normally /opt/demo). Safe to re-run; also executed automatically by an OTA
# "file-download" package.

set -e
cd "$(dirname "$0")"
DEMO_DIR="$(pwd)"

echo "=== RZ/G3E Vision Demo - Install ($DEMO_DIR) ==="

# The RZ/G3E Yocto image has no pip; the /IOTCONNECT Lite SDK is installed from
# source by renesas-rzg3e-evk/scripts/deps-install.sh. Just verify it is there.
python3 - <<'EOF'
import sys
try:
    import cv2, numpy
    from avnet.iotconnect.sdk.lite import Client, __version__
except ImportError as e:
    sys.exit(f'ERROR: {e}\nInstall the SDK first: see renesas-rzg3e-evk/README.md section 5.')
assert hasattr(cv2, 'FaceDetectorYN') and hasattr(cv2, 'FaceRecognizerSF'), 'OpenCV build lacks FaceDetectorYN/FaceRecognizerSF'
print(f'OpenCV {cv2.__version__}, numpy {numpy.__version__}, /IOTCONNECT SDK {__version__}: OK')
EOF

# Models (skipped when already present).
bash ./get-models.sh

# Load the uvcvideo driver now and on every boot (it is a module on this image
# and nothing else on a headless board pulls it in).
modprobe uvcvideo 2>/dev/null || true
if [ -d /etc/modules-load.d ] && ! grep -qs '^uvcvideo' /etc/modules-load.d/*.conf 2>/dev/null; then
    echo uvcvideo > /etc/modules-load.d/uvcvideo.conf
fi

mkdir -p faces models
chmod +x get-models.sh 2>/dev/null || true

# systemd service: start at boot, restart on failure. Only (re)started when not
# already running so an OTA re-install (which restarts app.py itself) is not
# disrupted.
cat > /etc/systemd/system/iotc-demo.service <<EOF
[Unit]
Description=IOTCONNECT RZ/G3E Vision Demo (app.py)
# Do NOT order after network-online.target: on this image ConnMan brings the
# link up while systemd-networkd-wait-online hangs, so that target never
# activates and the demo would never start. The app retries the cloud itself.
After=network.target connman.service
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=$DEMO_DIR
ExecStart=/usr/bin/python3 -u $DEMO_DIR/app.py
Restart=always
RestartSec=10
StandardOutput=append:$DEMO_DIR/app.log
StandardError=append:$DEMO_DIR/app.log

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable iotc-demo.service >/dev/null 2>&1
if [ -f iotcDeviceConfig.json ] && [ -f device-cert.pem ] && [ -f device-pkey.pem ]; then
    if ! systemctl is-active --quiet iotc-demo.service; then
        systemctl start iotc-demo.service || true
    fi
    echo "Service iotc-demo enabled and started (log: $DEMO_DIR/app.log)"
else
    echo "Service iotc-demo enabled. Copy iotcDeviceConfig.json, device-cert.pem and"
    echo "device-pkey.pem into $DEMO_DIR then run: systemctl start iotc-demo"
fi

echo ""
echo "Installation complete."
echo "Live feeds: http://$(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -n1):8080/"
echo "Status:     systemctl status iotc-demo    Manual run: cd $DEMO_DIR && python3 app.py"
