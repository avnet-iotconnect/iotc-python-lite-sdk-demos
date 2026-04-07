#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# av (PyAV) has no aarch64 wheel on PyPI and requires pkg-config + FFmpeg dev
# headers to build from source — neither of which is present on OpenSTLinux.
# The board has libavcodec60 (FFmpeg 6.1.1) from its Yocto image, which matches
# the FFmpeg version shipped with Ubuntu 24.04. Download the pre-built arm64
# package from Ubuntu 24.04, extract the Python module, and register a dist-info
# record so pip treats av as already installed.
# dpkg-deb delegates zstd decompression to the zstd binary; Ubuntu 24.04 debs
# use zstd by default. Install it first so dpkg-deb can extract the package.
# libavdevice60 is not installed by default on OpenSTLinux but is required by
# the Ubuntu-built av (PyAV) shared extension.
apt-get install -y zstd libavdevice60

echo "Installing av (PyAV) from Ubuntu 24.04 arm64 package..."
UBUNTU_AV_DEB="python3-av_11.0.0-4build1_arm64.deb"
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
# On aarch64, pip wheels are available for all of these (cffi, numpy, websockets)
# so no apt workarounds or --no-build-isolation flags are needed.
python3 -m pip install \
  "aiortc==1.9.0" \
  "websockets==13.0.1" \
  "boto3" \
  "numpy" \
  "requests"

# GStreamer is pre-installed on OpenSTLinux via the Yocto build; no apt install needed.

echo "Installation complete!"
