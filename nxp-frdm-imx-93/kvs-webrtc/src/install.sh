#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# The NXP i.MX93 Yocto image ships with numpy pre-installed, and PyPI provides
# manylinux aarch64 wheels for all other dependencies (aiortc, av/PyAV,
# websockets, boto3, cffi). No system package manager steps are required —
# a straightforward pip install handles everything.

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
python3 -m pip install --upgrade iotconnect-sdk-lite

# Install WebRTC and supporting Python dependencies.
# boto3 provides the AWS API clients used by app_webrtc.py for KVS signaling.
# aiortc handles WebRTC peer connections and media encoding (pulls in av/PyAV).
# websockets handles the KVS signaling WebSocket connection.
python3 -m pip install aiortc websockets boto3 requests

echo "Installation complete!"
