#!/bin/bash

# Define the source directory and output file
SRC_DIR="./src"
OUTPUT_FILE="package.tar.gz"

# Check if src directory exists
if [ ! -d "$SRC_DIR" ]; then
  echo "Error: '$SRC_DIR' directory not found."
  exit 1
fi

# Create a temporary directory
TMP_DIR=$(mktemp -d)

# Copy only files (no paths) to the temporary directory
find "$SRC_DIR" -type f -exec cp {} "$TMP_DIR" \;

# Create the tar.gz file from the temporary directory contents
tar -czf "$OUTPUT_FILE" -C "$TMP_DIR" .

# Clean up temporary directory
rm -rf "$TMP_DIR"

echo "Archive created: $OUTPUT_FILE"

