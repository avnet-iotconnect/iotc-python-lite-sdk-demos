#!/bin/bash

# Get the current directory (the directory where the script is located)
script_dir=$(dirname "$(realpath "$0")")

# Define source and destination directories
source_dir="$script_dir/../python-files"
core_files_dir="$script_dir/../../../files/core-files"
ota_files_dir="$script_dir/../../../files/ota-files"

# Define the files to be copied
dms_processing_file="$source_dir/dms-processing.py"
app_file="$source_dir/app.py"
install_sh_file="$script_dir/install.sh"

# Copy files to the target directories
echo "Copying files to $core_files_dir..."
cp "$dms_processing_file" "$core_files_dir"
cp "$app_file" "$core_files_dir"

echo "Copying install.sh to $ota_files_dir..."
cp "$install_sh_file" "$ota_files_dir"

echo "Files copied successfully."
