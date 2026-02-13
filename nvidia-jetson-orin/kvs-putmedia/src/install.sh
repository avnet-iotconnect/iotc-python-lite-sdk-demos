#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
# python3 -m pip install --force-reinstall iotconnect-sdk-lite
# ---------------------------------------------------------------------

export PIP_ROOT_USER_ACTION=ignore

# Install Python dependencies
PIP_ROOT_USER_ACTION=ignore python3 -m pip install requests

# Install GStreamer and build dependencies for AWS KVS Producer SDK
apt-get update
apt-get install -y \
  automake \
  build-essential \
  cmake \
  git \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-base-apps \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-tools \
  libcurl4-openssl-dev \
  libgstreamer1.0-dev \
  libgstreamer-plugins-base1.0-dev \
  liblog4cplus-dev \
  libssl-dev \
  pkg-config

# Build AWS KVS Producer SDK with GStreamer kvssink plugin
KVS_SDK_DIR="/opt/kvs-producer-sdk-cpp"

if [ ! -f "$KVS_SDK_DIR/build/libgstkvssink.so" ]; then
  echo "Building AWS KVS Producer SDK..."

  mkdir -p "$KVS_SDK_DIR"

  if [ ! -d "$KVS_SDK_DIR/.git" ]; then
    git clone https://github.com/awslabs/amazon-kinesis-video-streams-producer-sdk-cpp.git "$KVS_SDK_DIR"
  fi

  mkdir -p "$KVS_SDK_DIR/build"
  cd "$KVS_SDK_DIR/build"

  # Configure build with GStreamer plugin enabled
  cmake .. -DBUILD_GSTREAMER_PLUGIN=ON -DBUILD_JNI=OFF -DBUILD_DEPENDENCIES=OFF

  # Build the SDK (this may take 10-15 minutes)
  make -j"$(nproc)"

  cd /opt/demo
else
  echo "KVS Producer SDK already built, skipping build step..."
fi

# Register KVS SDK shared libraries with the system linker so that
# libgstkvssink.so can resolve its dependencies at runtime
echo "/opt/kvs-producer-sdk-cpp/build" > /etc/ld.so.conf.d/kvs-producer-sdk.conf
ldconfig

# Symlink kvssink into GStreamer's system plugin directory so it is
# discoverable without needing the GST_PLUGIN_PATH environment variable.
# This is critical for OTA updates where app.py restarts itself via
# os.execv() and the new process would not have GST_PLUGIN_PATH set.
GST_PLUGIN_DIR=$(pkg-config --variable=pluginsdir gstreamer-1.0 2>/dev/null)
if [ -n "$GST_PLUGIN_DIR" ] && [ -d "$GST_PLUGIN_DIR" ]; then
  ln -sf /opt/kvs-producer-sdk-cpp/build/libgstkvssink.so "$GST_PLUGIN_DIR/"
  echo "Symlinked kvssink into $GST_PLUGIN_DIR"
else
  echo "WARNING: Could not determine GStreamer plugin directory via pkg-config."
  echo "Falling back to GST_PLUGIN_PATH environment variable."
fi

# Also set up GST_PLUGIN_PATH as a fallback in case the symlink approach
# does not work on this system
cat > /etc/profile.d/kvs-gstreamer.sh << 'ENVEOF'
export GST_PLUGIN_PATH=/opt/kvs-producer-sdk-cpp/build
ENVEOF
chmod 644 /etc/profile.d/kvs-gstreamer.sh

# Add user to video group for camera access
if [ -n "$SUDO_USER" ]; then
  usermod -a -G video "$SUDO_USER" 2>/dev/null
else
  usermod -a -G video "$USER" 2>/dev/null
fi

# Verify kvssink plugin
if gst-inspect-1.0 kvssink > /dev/null 2>&1; then
  echo "kvssink GStreamer plugin verified successfully"
else
  echo "WARNING: kvssink plugin could not be verified by gst-inspect-1.0."
  echo "You may need to log out and back in, or manually run:"
  echo "  export GST_PLUGIN_PATH=/opt/kvs-producer-sdk-cpp/build"
  echo "Then verify with: gst-inspect-1.0 kvssink"
fi

echo "Installation complete!"
