#!/bin/bash

# Define the current directory and the parent directory
CURRENT_DIR=$(pwd)
PARENT_DIR=$(dirname "$CURRENT_DIR")
ADDITIONAL_MODELS_DIR="$PARENT_DIR/additional-models"

# Define the output tar.gz file name
OUTPUT_PACKAGE="ota-package.tar.gz"

# Files to include in the package
FILES_TO_INCLUDE=(
    "$CURRENT_DIR/ota-install.sh"
    "$PARENT_DIR/dms-processing.py"
    "$PARENT_DIR/imx93-ai-demo.py"
    "$PARENT_DIR/download_models.py"
)

# Find all .tflite files in the additional_models directory
TFLITE_FILES=$(find "$ADDITIONAL_MODELS_DIR" -name "*.tflite")

# Temporary directory to store files with only filenames (no paths)
TEMP_DIR=$(mktemp -d)

# Copy the files into the temporary directory
for file in "${FILES_TO_INCLUDE[@]}"; do
    cp "$file" "$TEMP_DIR"
done

# Copy the .tflite files into the temporary directory
for tflite in $TFLITE_FILES; do
    cp "$tflite" "$TEMP_DIR"
done

# Create the tar.gz package with files only containing their base names
tar -czvf "$OUTPUT_PACKAGE" -C "$TEMP_DIR" .

# Remove the temporary directory
rm -rf "$TEMP_DIR"

# Confirm the creation of the package
echo "Package $OUTPUT_PACKAGE created successfully."
