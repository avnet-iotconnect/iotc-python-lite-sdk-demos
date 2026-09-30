#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
#
# Build package.tar.gz from ./src for deployment or OTA ("file-download" command).
# Model files and the face gallery are NOT included: install.sh fetches the
# models on the board, and the gallery is device-local data.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

tar -czf package.tar.gz -C ./src \
    --exclude='models' --exclude='faces' --exclude='config.json' \
    --exclude='*.pem' --exclude='iotcDeviceConfig.json' --exclude='__pycache__' --exclude='*.log' \
    .
echo "Package created: $(pwd)/package.tar.gz"
echo "Files included:"
tar -tzf package.tar.gz
