#!/bin/bash

# Get the current directory of the script
SCRIPT_DIR=$(dirname "$0")

# Define the parent directory (one level up from the script location)
PARENT_DIR=$(realpath "$SCRIPT_DIR/..")

# Define the directories and file locations
CORE_FILES_DIR="$PARENT_DIR/core-files"
ADDITIONAL_FILES_DIR="$PARENT_DIR/additional-files"
OTA_INSTALL_FILE="$SCRIPT_DIR/ota-install.sh"

# Define the output archive file name
OUTPUT_ARCHIVE="$SCRIPT_DIR/compressed-files.tar.gz"

# Create a temporary directory to store files without their original paths
TEMP_DIR=$(mktemp -d)

# Copy the relevant files to the temporary directory (without path structure)
cp -r "$CORE_FILES_DIR"/* "$TEMP_DIR"
cp -r "$ADDITIONAL_FILES_DIR"/* "$TEMP_DIR"
cp "$OTA_INSTALL_FILE" "$TEMP_DIR"

# Create the tar.gz archive
tar -czf "$OUTPUT_ARCHIVE" -C "$TEMP_DIR" .

# Clean up by removing the temporary directory
rm -rf "$TEMP_DIR"

echo "Files have been compressed into $OUTPUT_ARCHIVE"
