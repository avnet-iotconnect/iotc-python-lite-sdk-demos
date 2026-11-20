#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

export PIP_ROOT_USER_ACTION=ignore

# Ubuntu 24.04 marks the system Python as externally managed (PEP 668).
if ! python3 -m pip install --upgrade iotconnect-sdk-lite requests --break-system-packages; then
    echo "ERROR: dependency install failed; not marking installation complete." >&2
    exit 1
fi

# The AMD FOC Motor Control stack is a one-time apt install (needs sudo and
# the Xilinx PPAs), so it is a documented prerequisite rather than something
# this script attempts during OTA. Warn if it is missing.
if ! dpkg -s xlnx-app-kd240-foc-motor-ctrl >/dev/null 2>&1; then
    echo "WARNING: xlnx-app-kd240-foc-motor-ctrl is not installed."
    echo "Follow the README prerequisites: add ppa:xilinx-apps, ppa:ubuntu-xilinx/default,"
    echo "and ppa:lely/ppa, apt install xlnx-firmware-kd240-motor-ctrl-qei"
    echo "xlnx-app-kd240-foc-motor-ctrl, then: sudo xmutil unloadapp && sudo xmutil loadapp kd240-motor-ctrl-qei"
fi

# When run as root (sudo bash ./install.sh, or an OTA under the running demo),
# install and enable the boot service so the demo starts on power-up.
if [ "$(id -u)" -eq 0 ] && [ -d /etc/systemd/system ] && [ -f /opt/demo/iotc-motor-ai.service ]; then
    cp /opt/demo/iotc-motor-ai.service /etc/systemd/system/iotc-motor-ai.service
    chmod 644 /etc/systemd/system/iotc-motor-ai.service
    systemctl daemon-reload
    systemctl enable iotc-motor-ai.service >/dev/null 2>&1
    echo "Boot service installed and enabled (journalctl -u iotc-motor-ai -f to watch)."
else
    echo "NOTE: run install.sh with sudo to install the boot service (iotc-motor-ai)."
fi

echo "Installation complete!"
