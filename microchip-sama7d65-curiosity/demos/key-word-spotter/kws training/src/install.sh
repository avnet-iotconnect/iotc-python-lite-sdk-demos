#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

set -e

export PIP_ROOT_USER_ACTION=ignore

PYTHON_BIN="${KWS_PYTHON_BIN:-/usr/bin/python3}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

echo "Using Python interpreter: ${PYTHON_BIN}"

if "${PYTHON_BIN}" -m pip install -r requirements.txt; then
  echo "Verified Python package availability for Flask, boto3, requests, paho-mqtt, and iotconnect-sdk-lite."
else
  echo "WARNING: Unable to install one or more Python dependencies automatically."
  echo "The UI can still run if compatible packages are already present on the board."
fi

if command -v arecord >/dev/null 2>&1; then
  echo "Verified ALSA capture command: arecord"
else
  echo "WARNING: arecord is not available."
  echo "Install alsa-utils on the board if audio capture fails."
fi

echo "Run the app with: ${PYTHON_BIN} ./training_app.py"
echo "Installation complete."
