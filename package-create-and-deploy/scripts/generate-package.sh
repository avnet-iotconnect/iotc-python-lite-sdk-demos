#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set the source and destination paths
SOURCE_DIR="$SCRIPT_DIR/../package-contents"
DEST_TAR="$SCRIPT_DIR/../install-package.tar.gz"

# Create the tar.gz archive without including paths
# The -C option changes to the directory before adding files
# This way only filenames (not paths) are stored
tar -czf "$DEST_TAR" -C "$SOURCE_DIR" .

echo "Archive created at: $DEST_TAR"
