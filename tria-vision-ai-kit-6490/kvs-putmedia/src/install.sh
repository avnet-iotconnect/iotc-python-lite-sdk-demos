#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore

# Upgrade iotconnect-sdk-lite to ensure KVS / vs_cb support is present
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade iotconnect-sdk-lite

# Install Python dependencies
PIP_ROOT_USER_ACTION=ignore python3 -m pip install requests

# Install pre-built KVS Producer SDK shared libraries.
# The QCS6490 Yocto image has the Qualcomm msm_vidc hardware H264 encoder
# accessible via v4l2h264enc, so no bundled software encoder is needed —
# only the KVS SDK libraries are required.
# The libs/ directory is extracted alongside this script from the OTA package.
KVS_BUILD_DIR="/opt/kvs-producer-sdk-cpp/build"
LIBS_DIR="$(dirname "$0")/libs"

mkdir -p "$KVS_BUILD_DIR"

if ls "$LIBS_DIR"/*.so* > /dev/null 2>&1; then
  echo "Installing pre-built KVS SDK libraries from $LIBS_DIR..."
  cp "$LIBS_DIR"/*.so* "$KVS_BUILD_DIR/"
  # Remove any bundled libcurl — the system's libcurl must be used
  rm -f "$KVS_BUILD_DIR"/libcurl*.so*
  echo "Installed $(ls "$KVS_BUILD_DIR"/*.so* | wc -l) library files to $KVS_BUILD_DIR"
else
  echo "ERROR: No pre-built libraries found in $LIBS_DIR"
  exit 1
fi

# Create SONAME symlinks for versioned libraries (e.g., libcproducer.so.1 -> libcproducer.so.1.6.1).
cd "$KVS_BUILD_DIR"
for full in *.so.*.*.*; do
  [ -f "$full" ] || continue
  soname="${full%.*.*}"  # strip last two version components: foo.so.1.6.1 -> foo.so.1
  [ -e "$soname" ] || ln -sf "$full" "$soname"
done
cd /opt/demo

# Register KVS SDK shared libraries with the system linker.
# On the QCS6490 Yocto image, /etc/ld.so.conf.d/ does not exist by default
# even though /etc/ld.so.conf references it, so create it if needed.
mkdir -p /etc/ld.so.conf.d
echo "$KVS_BUILD_DIR" > /etc/ld.so.conf.d/kvs-producer-sdk.conf
ldconfig

# Locate the GStreamer system plugin directory.
GST_PLUGIN_DIR=$(find /usr/lib -maxdepth 4 -type d -name "gstreamer-1.0" 2>/dev/null | head -1)

if [ -n "$GST_PLUGIN_DIR" ] && [ -d "$GST_PLUGIN_DIR" ]; then
  ln -sf "$KVS_BUILD_DIR/libgstkvssink.so" "$GST_PLUGIN_DIR/"
  echo "Symlinked kvssink into $GST_PLUGIN_DIR"
else
  echo "WARNING: Could not locate GStreamer system plugin directory."
  echo "Falling back to GST_PLUGIN_PATH environment variable."
fi

# Set up GST_PLUGIN_PATH and LD_LIBRARY_PATH for KVS SDK
cat > /etc/profile.d/kvs-gstreamer.sh << 'ENVEOF'
export GST_PLUGIN_PATH=/opt/kvs-producer-sdk-cpp/build
export LD_LIBRARY_PATH=/opt/kvs-producer-sdk-cpp/build${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
ENVEOF
chmod 644 /etc/profile.d/kvs-gstreamer.sh

# Verify kvssink plugin
if gst-inspect-1.0 kvssink > /dev/null 2>&1; then
  echo "kvssink GStreamer plugin verified successfully"
else
  echo "WARNING: kvssink plugin could not be verified by gst-inspect-1.0."
  echo "You may need to log out and back in, or manually run:"
  echo "  export GST_PLUGIN_PATH=/opt/kvs-producer-sdk-cpp/build"
  echo "Then verify with: gst-inspect-1.0 kvssink"
fi

# Clear GStreamer plugin registry cache so kvssink is rescanned cleanly on next run.
# Without this, a stale cache entry (from a prior failed load) causes "No such element or plugin 'kvssink'".
rm -rf ~/.cache/gstreamer-1.0/
echo "Cleared GStreamer registry cache"

echo "Installation complete!"
