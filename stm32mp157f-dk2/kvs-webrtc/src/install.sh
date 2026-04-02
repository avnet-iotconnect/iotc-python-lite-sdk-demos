#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade iotconnect-sdk-lite

# cffi 2.0.0 is source-only for ARM (no pre-built wheel) and requires a C compiler
# that is not present on OpenSTLinux. Pin to 1.x which ships armv7l/aarch64 wheels.
PIP_ROOT_USER_ACTION=ignore python3 -m pip install "cffi>=1.14.0,<2.0.0"

# Install WebRTC and supporting Python dependencies.
# boto3 provides the AWS API clients used by app_webrtc.py for KVS signaling.
# av and aiortc handle WebRTC peer connections and media encoding.
# websockets handles the KVS signaling WebSocket connection.
# numpy is used to pass raw video frames between GStreamer capture and aiortc.
PIP_ROOT_USER_ACTION=ignore python3 -m pip install \
  "aiortc==1.9.0" \
  "av" \
  "websockets==13.0.1" \
  "boto3" \
  "numpy" \
  "requests"

# GStreamer is pre-installed on OpenSTLinux via the Yocto build; no apt install needed.

echo "Installation complete!"
