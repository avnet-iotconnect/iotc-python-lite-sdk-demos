#!/bin/bash

KVS_LIBS_DIR="$HOME/kvs-libs"
SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"
STAGING_DIR="/tmp/kvs-package-staging"

# Verify pre-built KVS libs exist
if ! ls "$KVS_LIBS_DIR"/*.so* > /dev/null 2>&1; then
  echo "ERROR: No .so files found in $KVS_LIBS_DIR"
  echo "Run ~/kvs-build.sh first to build the KVS SDK libraries."
  exit 1
fi

# Set up staging directory
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

# Copy source files
cp -r "$SRC_DIR"/. "$STAGING_DIR/"

# Copy pre-built KVS SDK libs into libs/ subdirectory
mkdir -p "$STAGING_DIR/libs"
cp "$KVS_LIBS_DIR"/*.so* "$STAGING_DIR/libs/"
echo "Bundled $(ls "$STAGING_DIR/libs/" | wc -l) KVS library files into package."

# Create the archive
tar -czf "$ARCHIVE_NAME" -C "$STAGING_DIR" .
cp "$ARCHIVE_NAME" ../../common/

# Clean up staging dir
rm -rf "$STAGING_DIR"

echo "Created archive $ARCHIVE_NAME and copied it into the common directory."
