#!/bin/bash

set -e

SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"
STAGING_DIR="/tmp/sama7d65-wifi-rnwf11-package"
PACKAGES_DIR="./packages"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

cp -r "$SRC_DIR"/. "$STAGING_DIR/"
find "$STAGING_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$STAGING_DIR" -type f -name "*.pyc" -delete
chmod +x "$STAGING_DIR/install.sh"

tar -czf "./$ARCHIVE_NAME" -C "$STAGING_DIR" .

cp "./$ARCHIVE_NAME" ../../common/
mkdir -p "$PACKAGES_DIR"
cp "./$ARCHIVE_NAME" "$PACKAGES_DIR/wifi-rnwf11-package.tar.gz"

rm -rf "$STAGING_DIR"

echo "Created archive $ARCHIVE_NAME and copied it into the repo common and local packages directories."
