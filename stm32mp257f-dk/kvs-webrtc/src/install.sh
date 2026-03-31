#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade iotconnect-sdk-lite

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

# Ensure GStreamer v4l2src (USB camera capture) plugin is available.
# On OpenSTLinux this is typically pre-installed; this is a no-op if already present.
apt-get update -qq
apt-get install -y gstreamer1.0-plugins-good gstreamer1.0-tools || true

echo "Installation complete!"
