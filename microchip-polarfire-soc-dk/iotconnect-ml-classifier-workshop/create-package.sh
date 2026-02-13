#!/bin/bash
set -euo pipefail

SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"

tar -czf "$ARCHIVE_NAME" -C "$SRC_DIR" .
echo "Created $ARCHIVE_NAME"
