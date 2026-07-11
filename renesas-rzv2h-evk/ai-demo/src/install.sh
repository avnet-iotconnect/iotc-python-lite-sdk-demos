#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

set -e
export PIP_ROOT_USER_ACTION=ignore

echo "=== RZ/V2H AI Demo — Install ==="

# Upgrade IoTConnect SDK and install runtime dependencies.
# OpenCV 4.9.0 and numpy 1.26.4 are pre-installed on the RZ/V2H Yocto image.
python3 -m pip install --upgrade iotconnect-sdk-lite requests

# Verify OpenCV and its Haar cascade data are accessible.
python3 -c "
import cv2, os
# RZ/V2H Yocto build stores cascades here; cv2.data is not available in this build
HAAR_DIR = '/usr/share/opencv4/haarcascades'
face_xml = os.path.join(HAAR_DIR, 'haarcascade_frontalface_default.xml')
body_xml = os.path.join(HAAR_DIR, 'haarcascade_fullbody.xml')
print(f'OpenCV {cv2.__version__} found at: {cv2.__file__}')
print(f'Haar cascades path: {HAAR_DIR}')
print(f'Face cascade: {\"OK\" if os.path.exists(face_xml) else \"MISSING\"}')
print(f'Body cascade: {\"OK\" if os.path.exists(body_xml) else \"MISSING\"}')
"

# Enable Weston output-capture (--debug) so the /drpai live web feed can
# screenshot the compositor. Idempotent — only touches Weston when the
# override is missing, so OTA re-installs don't disrupt a running demo.
WESTON_DROPIN=/etc/systemd/system/weston.service.d/override.conf
if ! grep -qs -- '--debug' "$WESTON_DROPIN"; then
    mkdir -p /etc/systemd/system/weston.service.d
    cat > "$WESTON_DROPIN" << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/weston --modules=systemd-notify.so --idle-time=0 --debug
EOF
    systemctl daemon-reload
    systemctl restart weston || true
    echo "Weston output-capture enabled for the /drpai web feed"
fi

# Verify DRP-AI demo binaries are available.
echo ""
echo "Checking DRP-AI demo binaries..."
MODES=("coco" "animal" "vehicle")
for mode in "${MODES[@]}"; do
    if [ -f "/home/weston/tvm_q08/object_counter" ]; then
        echo "  object_counter ($mode): OK"
    else
        echo "  object_counter ($mode): NOT FOUND — follow the AI SDK setup guide"
        echo "    Expected: /home/weston/tvm_q08/object_counter"
    fi
    break
done

echo ""
echo "Installation complete!"
echo "Run with: cd /opt/demo && python3 app.py"
