#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# Restore the system pip from the Yocto package feed.
# pip cannot be upgraded via pip itself on this image: Python 3.12 on OpenSTLinux
# has tomllib stripped, and pip>=25 imports tomllib at startup, breaking all pip calls.
# Reinstalling via apt always gives a known-good version that works with this Python build.
apt-get install -y --reinstall python3-pip 2>/dev/null || true

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade iotconnect-sdk-lite

# cffi has no pre-built wheel for armv7l on PyPI and requires a C compiler to build
# from source.  The OpenSTLinux Yocto image does not include GCC, so we install cffi
# via the system package manager instead (shipped as a compiled Yocto package).
apt-get install -y python3-cffi 2>/dev/null || true

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
