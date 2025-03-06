#!/bin/bash

# Define the target directories
target_dir_tflite="/usr/bin/eiq-examples-git/models"

# Loop through each file in the current directory
for file in *; do
  # Check if it's a file (not a directory)
  if [ -f "$file" ]; then
    case "$file" in
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
