#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# cffi has no pre-built wheel for armv7l on PyPI and requires a C compiler to build
# from source. The OpenSTLinux Yocto image does not include GCC, so we install cffi
# via the system package manager (shipped as a compiled Yocto package).
apt-get install -y python3-cffi

# Python 3.12 normally ships tomllib in its stdlib, but this Yocto build strips it.
# setuptools (>=67) imports tomllib when processing pyproject.toml files, so all
# source-package builds fail without it. Install the pure-Python backport (tomli)
# and create a stdlib-level shim so that 'import tomllib' resolves correctly.
# tomli is a pure-Python wheel — no C compiler or tomllib needed to install it.
python3 -c "import tomllib" 2>/dev/null || {
    python3 -m pip install --quiet tomli
    printf 'from tomli import load, loads\n' > /usr/lib/python3.12/tomllib.py
}

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
python3 -m pip install --upgrade iotconnect-sdk-lite

# Install WebRTC and supporting Python dependencies.
# boto3 provides the AWS API clients used by app_webrtc.py for KVS signaling.
# av and aiortc handle WebRTC peer connections and media encoding.
# websockets handles the KVS signaling WebSocket connection.
# numpy is used to pass raw video frames between GStreamer capture and aiortc.
#
# --no-build-isolation skips pip's isolated build environment for source packages.
# Without it, pip creates a fresh venv for aiortc's build, installs cffi 2.0.0
# (source-only, needs C compiler) into that venv, and fails. With this flag, pip
# uses the current environment instead, where cffi 1.16.0 (from apt) is already
# present and the tomllib shim above makes setuptools work correctly.
python3 -m pip install --no-build-isolation \
  "aiortc==1.9.0" \
  "av" \
  "websockets==13.0.1" \
  "boto3" \
  "numpy" \
  "requests"

# GStreamer is pre-installed on OpenSTLinux via the Yocto build; no apt install needed.

echo "Installation complete!"
