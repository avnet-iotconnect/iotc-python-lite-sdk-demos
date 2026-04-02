#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade iotconnect-sdk-lite

# cffi has no pre-built wheel for armv7l on PyPI and requires a C compiler to build
# from source.  The OpenSTLinux Yocto image does not include GCC, so we install cffi
# via the system package manager instead (shipped as a compiled Yocto package).
# The apt call is allowed to fail gracefully in case the feed is unavailable;
# pip will then attempt its own install and produce a clear error if it also fails.
apt-get install -y python3-cffi 2>/dev/null || true

# The system pip on OpenSTLinux is old and does not recognise the manylinux_2_17_armv7l
# wheel tag.  The system setuptools is also broken on this Yocto Python build: it tries
# to import tomllib (stripped from this image) and fails before any build can start.
# Upgrading both tools ensures pip can resolve wheels for remaining packages.
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade pip setuptools

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
