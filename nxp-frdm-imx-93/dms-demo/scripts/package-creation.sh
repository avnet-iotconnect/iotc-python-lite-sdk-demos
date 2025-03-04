#!/bin/bash

# Define the current directory and the directories for the other files
CURRENT_DIR=$(pwd)
PARENT_DIR=$(dirname "$CURRENT_DIR")
ADDITIONAL_MODELS_DIR="$PARENT_DIR/additional-models"

# Define the output tar.gz file name
OUTPUT_PACKAGE="package_creation.tar.gz"

# Files to include in the package
FILES_TO_INCLUDE=(
    "$CURRENT_DIR/ota-install.sh"
    "$PARENT_DIR/dms-processing.py"
    "$PARENT_DIR/imx93-ai-demo.py"
    "$PARENT_DIR/download_models.py"
)

# Find all .tflite files in the additional_models directory
TFLITE_FILES=$(find "$ADDITIONAL_MODELS_DIR" -name "*.tflite")

# Create the tar.gz package
tar -czvf "$OUTPUT_PACKAGE" "${FILES_TO_INCLUDE[@]}" $TFLITE_FILES

# Confirm the creation of the package
echo "Package $OUTPUT_PACKAGE created successfully."
