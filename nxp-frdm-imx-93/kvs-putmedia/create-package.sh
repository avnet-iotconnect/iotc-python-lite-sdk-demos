#!/bin/bash

KVS_LIBS_DIR="$HOME/kvs-libs-imx93"
SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"
STAGING_DIR="/tmp/kvs-package-staging"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

cp -r "$SRC_DIR"/. "$STAGING_DIR/"
mkdir -p "$STAGING_DIR/libs"

if ls "$KVS_LIBS_DIR"/*.so* > /dev/null 2>&1; then
  cp "$KVS_LIBS_DIR"/*.so* "$STAGING_DIR/libs/"
  echo "Bundled $(ls "$STAGING_DIR/libs/" | wc -l) library files from $KVS_LIBS_DIR."
elif [ -f "$ARCHIVE_NAME" ]; then
  echo "Using bundled libraries from existing $ARCHIVE_NAME."
  tar -xzf "$ARCHIVE_NAME" -C "$STAGING_DIR" ./libs
  echo "Bundled $(ls "$STAGING_DIR/libs/" | wc -l) library files from existing archive."
else
  echo "ERROR: No .so files found in $KVS_LIBS_DIR and no existing $ARCHIVE_NAME available."
  exit 1
fi

tar -czf "$ARCHIVE_NAME" -C "$STAGING_DIR" .
cp "$ARCHIVE_NAME" ../../common/

rm -rf "$STAGING_DIR"

echo "Created archive $ARCHIVE_NAME and copied it into the common directory."
