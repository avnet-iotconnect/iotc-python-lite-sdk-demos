#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
# python3 -m pip install --force-reinstall iotconnect-sdk-lite
# ---------------------------------------------------------------------

# install and set up x-linux-ai packages
apt-get install x-linux-ai-tool -y
apt-get update
x-linux-ai -i packagegroup-x-linux-ai-demo-cpu
systemctl restart weston-graphical-session.service

# move ai vision files to appropriate directory
DEST_DIR="/usr/local/x-linux-ai/object-detection"
mv launch-vision-program.sh "$DEST_DIR"
mv iotc-vision-program.py "$DEST_DIR"

echo "Installation complete!"
