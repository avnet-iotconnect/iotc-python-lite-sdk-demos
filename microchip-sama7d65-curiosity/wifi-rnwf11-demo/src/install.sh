#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

set -e

export PIP_ROOT_USER_ACTION=ignore

if python3 -m pip install --break-system-packages iotconnect-sdk-lite pyserial; then
  echo "Verified Python package availability for iotconnect-sdk-lite and pyserial."
else
  echo "WARNING: Unable to install packages automatically."
  echo "The app can still run if compatible versions are already present on the board."
fi

echo "Installation complete."
