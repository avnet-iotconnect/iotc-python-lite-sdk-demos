#!/bin/bash

SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"
STAGING_DIR="/tmp/kvs-webrtc-package-staging"

# Set up staging directory
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

# Copy source files
cp -r "$SRC_DIR"/. "$STAGING_DIR/"

# Create the archive
tar -czf "$ARCHIVE_NAME" -C "$STAGING_DIR" .

# Clean up staging dir
rm -rf "$STAGING_DIR"

echo "Created archive $ARCHIVE_NAME"
