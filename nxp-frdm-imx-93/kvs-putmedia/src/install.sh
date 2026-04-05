#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

set -e

export PIP_ROOT_USER_ACTION=ignore

BUNDLE_LIB_PATH="/opt/video-upload-libs"
LIBS_DIR="$(dirname "$0")/libs"

# Install Python dependencies, including the optional boto3 support used by Client.s3_upload().
python3 -m pip install --upgrade "iotconnect-sdk-lite[aws-s3]" requests

mkdir -p "$BUNDLE_LIB_PATH"

if ls "$LIBS_DIR"/*.so* > /dev/null 2>&1; then
  echo "Installing bundled video libraries from $LIBS_DIR..."
  cp "$LIBS_DIR"/*.so* "$BUNDLE_LIB_PATH/"
  echo "Installed $(ls "$BUNDLE_LIB_PATH"/*.so* | wc -l) library files into $BUNDLE_LIB_PATH"
else
  echo "ERROR: No bundled libraries found in $LIBS_DIR"
  exit 1
fi

cd "$BUNDLE_LIB_PATH"
for full in *.so.*.*.*; do
  [ -f "$full" ] || continue
  soname="${full%.*.*}"
  [ -e "$soname" ] || ln -sf "$full" "$soname"
done
[ -e libx264.so ] || ln -sf libx264.so.164 libx264.so 2>/dev/null || true
cd /opt/demo

mkdir -p /etc/ld.so.conf.d
echo "$BUNDLE_LIB_PATH" > /etc/ld.so.conf.d/video-upload.conf
ldconfig

GST_PLUGIN_DIR=$(find /usr/lib -maxdepth 4 -type d -name "gstreamer-1.0" 2>/dev/null | head -1)
if [ -n "$GST_PLUGIN_DIR" ] && [ -d "$GST_PLUGIN_DIR" ]; then
  if [ -f "$BUNDLE_LIB_PATH/libgstx264.so" ]; then
    cp "$BUNDLE_LIB_PATH/libgstx264.so" "$GST_PLUGIN_DIR/"
    echo "Installed libgstx264.so into $GST_PLUGIN_DIR"
  fi
else
  echo "WARNING: Could not locate the system GStreamer plugin directory."
  echo "The app will rely on GST_PLUGIN_PATH=$BUNDLE_LIB_PATH at runtime."
fi

cat > /etc/profile.d/video-upload-gstreamer.sh << EOF
export GST_PLUGIN_PATH=$BUNDLE_LIB_PATH\${GST_PLUGIN_PATH:+:\$GST_PLUGIN_PATH}
export LD_LIBRARY_PATH=$BUNDLE_LIB_PATH\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}
EOF
chmod 644 /etc/profile.d/video-upload-gstreamer.sh

rm -rf ~/.cache/gstreamer-1.0/
echo "Cleared GStreamer registry cache"

for plugin in x264enc mp4mux splitmuxsink; do
  if gst-inspect-1.0 "$plugin" > /dev/null 2>&1; then
    echo "Verified GStreamer plugin: $plugin"
  else
    echo "WARNING: GStreamer plugin could not be verified: $plugin"
  fi
done

echo "Installation complete."
