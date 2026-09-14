#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# Ubuntu Server 24.04 (the OS used by this board's quickstart) enforces PEP 668
# ("externally managed environment"), so pip refuses to install into the system
# environment unless told to.
PIP_BREAK="--break-system-packages"

apt-get update

# Install GStreamer's video4linux2 plugin for USB camera capture. Ubuntu Server
# does not ship GStreamer by default, unlike the multimedia-focused Yocto images
# used by other boards in this repo.
apt-get install -y gstreamer1.0-plugins-good gstreamer1.0-tools

# numpy has a spotty history of aarch64 wheel availability on PyPI for some
# Python builds and can otherwise trigger a slow from-source build; install it
# via apt instead, matching the approach used for other aarch64 boards in this repo.
# python3-pip is included since Ubuntu Server's minimal install ships the Python
# interpreter without it.
apt-get install -y python3-numpy python3-pip

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
python3 -m pip install $PIP_BREAK --upgrade iotconnect-sdk-lite

# Install WebRTC and supporting Python dependencies.
# boto3 provides the AWS API clients used by app_webrtc.py for KVS signaling.
# aiortc handles WebRTC peer connections and media encoding (pulls in av/PyAV).
# PyPI provides manylinux aarch64 wheels for aiortc, av, cffi, and websockets,
# so no system package workarounds are required beyond numpy above.
# websockets handles the KVS signaling WebSocket connection.
python3 -m pip install $PIP_BREAK \
  aiortc \
  websockets \
  boto3 \
  requests

echo "Installation complete!"
