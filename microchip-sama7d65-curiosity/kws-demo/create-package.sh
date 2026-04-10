#!/bin/bash

set -e

SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"
STAGING_DIR="/tmp/sama7d65-kws-package"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

cp -r "$SRC_DIR"/. "$STAGING_DIR/"
find "$STAGING_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$STAGING_DIR" -type f -name "*.pyc" -delete

tar -czf "$ARCHIVE_NAME" -C "$STAGING_DIR" .
cp "./$ARCHIVE_NAME" ../../common/

rm -rf "$STAGING_DIR"

echo "Created archive $ARCHIVE_NAME and copied it into the common directory."
