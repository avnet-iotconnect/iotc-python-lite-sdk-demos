#!/bin/bash

# Get the current directory (the directory where the script is located)
script_dir=$(dirname "$(realpath "$0")")

# Define the paths for the core-files, additional-files, and install.sh
core_files_dir="$script_dir/../core-files"
additional_files_dir="$script_dir/../additional-files"
install_sh="$script_dir/install.sh"

# Define the tar.gz output file name
output_tar_gz="$script_dir/update-payload.tar.gz"

# Create the .tar.gz file
tar -czf "$output_tar_gz" -C "$core_files_dir" \
    $(find "$core_files_dir" -type f -exec basename {} \;) \
    -C "$additional_files_dir" \
    $(find "$additional_files_dir" -type f ! -name "placeholder.txt" -exec basename {} \;) \
    -C "$script_dir" \
    install.sh

echo "Update payload created successfully at $output_tar_gz"
