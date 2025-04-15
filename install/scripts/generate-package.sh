#!/bin/bash

# Name of the archive
archive_name="install-package.tar.gz"

# Get the name of the script itself
script_name=$(basename "$0")

# Create the archive, excluding the script and the archive itself
tar --exclude="./$script_name" --exclude="./$archive_name" -czf "$archive_name" ./*

echo "Created archive: $archive_name"
