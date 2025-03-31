#!/bin/bash

# Get the current directory (the directory where the script is located)
script_dir=$(dirname "$(realpath "$0")")

# Define the paths for the core-files, additional-files, and install.sh
core_files_dir="$script_dir/../core-files"
additional_files_dir="$script_dir/../additional-files"
install_sh="$script_dir/install.sh"

# Define the tar.gz output file name
output_tar_gz="$script_dir/ota-payload.tar.gz"

# Create the .tar.gz file
tar -czf "$output_tar_gz" -C "$script_dir" \
    $(find "$core_files_dir" -type f -exec basename {} \;) \
    $(find "$additional_files_dir" -type f ! -name "placeholder.txt" -exec basename {} \;) \
    install.sh \
    device-replacement.py

echo "OTA payload created successfully at $output_tar_gz"
