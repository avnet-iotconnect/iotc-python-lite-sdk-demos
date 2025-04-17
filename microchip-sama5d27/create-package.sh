#!/bin/bash

# Define variables
SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"

# Create the tar.gz archive containing only the files in src (no directory paths)
# The -C changes to the src directory, and . adds only the files from there
tar -czf "$ARCHIVE_NAME" -C "$SRC_DIR" .

cp ./package.tar.gz ../../common/

echo "Created archive $ARCHIVE_NAME located in the common directory."
