#!/bin/bash

# Get the current directory where the script is located
SCRIPT_DIR=$(dirname "$0")

# Define the parent directory (one directory up from the script location)
PARENT_DIR=$(realpath "$SCRIPT_DIR/..")

# Define the directories and file locations
CORE_FILES_DIR="$PARENT_DIR/core-files"
ADDITIONAL_FILES_DIR="$PARENT_DIR/additional-files"
OTA_INSTALL_FILE="$SCRIPT_DIR/ota-install.sh"

# Define the output archive file name
OUTPUT_ARCHIVE="$SCRIPT_DIR/compressed-files.tar.gz"

# Create a temporary directory to store files without their original paths
TEMP_DIR=$(mktemp -d)

# Copy files from core-files directory
find "$CORE_FILES_DIR" -type f -exec cp --no-dereference {} "$TEMP_DIR" \;

# Copy files from additional-files directory except placeholder.txt
find "$ADDITIONAL_FILES_DIR" -type f ! -name "placeholder.txt" -exec cp --no-dereference {} "$TEMP_DIR" \;

# Copy ota-install.sh file to the temporary directory
cp "$OTA_INSTALL_FILE" "$TEMP_DIR"

# Create the tar.gz archive (without path, just file names)
tar -czf "$OUTPUT_ARCHIVE" -C "$TEMP_DIR" .

# Clean up by removing the temporary directory
rm -rf "$TEMP_DIR"

echo "Files have been compressed into $OUTPUT_ARCHIVE"
