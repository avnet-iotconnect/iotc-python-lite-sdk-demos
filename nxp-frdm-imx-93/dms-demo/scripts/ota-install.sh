#!/bin/bash

# Define the target directories
target_dir_download_models="/usr/bin/eiq-examples-git"
target_dir_dms="/usr/bin/eiq-examples-git/dms"
target_dir_tflite="/usr/bin/eiq-examples-git/models"

# Loop through each file in the current directory
for file in *; do
  # Check if it's a file (not a directory)
  if [ -f "$file" ]; then
    case "$file" in
      "download_models.py")
        # Move download_models.py to /usr/bin/eiq-examples-git
        mv "$file" "$target_dir_download_models"
        echo "Moved $file to $target_dir_download_models"
        ;;
      "dms-processing.py")
        # Move dms-processing to /usr/bin/eiq-examples-git/dms
        mv "$file" "$target_dir_dms"
        echo "Moved $file to $target_dir_dms"
        ;;
      *.tflite)
        # Move .tflite files to /usr/bin/eiq-examples-git/models
        mv "$file" "$target_dir_tflite"
        echo "Moved $file to $target_dir_tflite"
        ;;
      *)
        # If the file doesn't match any condition, do nothing
        ;;
    esac
  fi
done
