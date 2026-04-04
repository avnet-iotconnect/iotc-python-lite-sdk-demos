#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# cffi has no armv7l wheel on PyPI and requires a C compiler to build from source.
# The OpenSTLinux Yocto image does not include GCC, so install via apt instead.
apt-get install -y python3-cffi

# numpy 2.x dropped armv7l wheels, causing pip to download a 20+ MB source tarball
# that exceeds /tmp space. Install the Yocto apt package instead.
apt-get install -y python3-numpy

# av (PyAV) has no armv7l wheel on PyPI, no FFmpeg dev headers in the OpenSTLinux
# apt feed, and no C compiler on the board — so it cannot be built from source.
# Download the pre-built armhf package from Ubuntu 24.04, which ships FFmpeg 6.1.x
# matching this board's libavcodec60/libavformat60/etc. (6.1.3). Extract the Python
# module files and register a dist-info record so pip treats av as already installed
# and does not attempt to rebuild it when resolving aiortc's dependencies.
echo "Installing av (PyAV) from Ubuntu 24.04 armhf package..."
UBUNTU_AV_DEB="python3-av_11.0.0-4build1_armhf.deb"
UBUNTU_AV_URL="http://ports.ubuntu.com/ubuntu-ports/pool/universe/p/python-av/${UBUNTU_AV_DEB}"
wget -q --show-progress -O "/tmp/${UBUNTU_AV_DEB}" "${UBUNTU_AV_URL}"
mkdir -p /tmp/av-deb-extract
dpkg-deb -x "/tmp/${UBUNTU_AV_DEB}" /tmp/av-deb-extract/
AV_MODULE_DIR=$(find /tmp/av-deb-extract -type d -name "av" | head -1)
if [ -z "$AV_MODULE_DIR" ]; then
    echo "ERROR: Could not find av module in extracted Ubuntu package"
    exit 1
fi
cp -r "$AV_MODULE_DIR" /usr/lib/python3.12/site-packages/
DIST_INFO="/usr/lib/python3.12/site-packages/av-11.0.0.dist-info"
mkdir -p "$DIST_INFO"
printf 'Metadata-Version: 2.1\nName: av\nVersion: 11.0.0\n' > "$DIST_INFO/METADATA"
printf 'pip\n' > "$DIST_INFO/INSTALLER"
rm -rf /tmp/av-deb-extract "/tmp/${UBUNTU_AV_DEB}"
python3 -c "import av; print(f'av {av.__version__} installed successfully')"

# Python 3.12 on this Yocto build has tomllib stripped from the stdlib.
# setuptools (>=67) imports tomllib when processing pyproject.toml files, so all
# source-package builds fail without it. Install the pure-Python backport (tomli)
# and create a stdlib-level shim so that 'import tomllib' resolves correctly.
python3 -c "import tomllib" 2>/dev/null || {
    python3 -m pip install --quiet tomli
    printf 'from tomli import load, loads\n' > /usr/lib/python3.12/tomllib.py
}

# Upgrade iotconnect-sdk-lite to ensure KVS WebRTC / vs_cb support is present
python3 -m pip install --upgrade iotconnect-sdk-lite

# Install WebRTC and supporting Python dependencies.
# boto3 provides the AWS API clients used by app_webrtc.py for KVS signaling.
# aiortc handles WebRTC peer connections and media encoding.
# websockets handles the KVS signaling WebSocket connection.
#
# --no-build-isolation skips pip's isolated build environment so source packages
# use the system cffi (from apt) and system setuptools (with our tomllib shim)
# rather than fetching incompatible versions into a fresh venv.
# av and numpy are excluded — both installed above outside of pip.
python3 -m pip install --no-build-isolation \
  "aiortc==1.9.0" \
  "websockets==13.0.1" \
  "boto3" \
  "requests"

# GStreamer is pre-installed on OpenSTLinux via the Yocto build; no apt install needed.

echo "Installation complete!"
