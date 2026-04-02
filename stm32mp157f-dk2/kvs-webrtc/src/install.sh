#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade iotconnect-sdk-lite

# The system pip on OpenSTLinux is old and does not recognise the manylinux_2_17_armv7l
# wheel tag, causing it to fall back to source tarballs that require a C compiler.
# The system setuptools is also broken on this Yocto Python build: it tries to
# import tomllib (stripped from this image) and fails before any build can start.
# Upgrading both tools first resolves both issues.
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade pip setuptools

# cffi 2.0.0 is source-only for ARM. 1.x ships a manylinux_2_17_armv7l wheel, but
# an up-to-date pip (above) is required to resolve that wheel tag correctly.
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
