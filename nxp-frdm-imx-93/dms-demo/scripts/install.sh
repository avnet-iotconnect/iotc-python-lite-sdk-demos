#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

set -e  # Stop script on first failure

echo "Updating environment variables..."
export PATH=$PATH:/usr/local/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

echo "Installing dependencies..."
PIP_ROOT_USER_ACTION=ignore python3 -m pip install flask numpy opencv-python requests filelock networkx

# move dms-processing.py

# move download_models.py 

# execute download_models.py

# Create empty dms-data.json with read/write perms
touch dms-data.json
chmod 666 dms-data.json

cp /usr/bin/eiq-examples-git/dms/face_detection.py .
cp /usr/bin/eiq-examples-git/dms/eye_landmark.py .
cp /usr/bin/eiq-examples-git/dms/face_landmark.py .
cp /usr/bin/eiq-examples-git/dms/utils.py .

# ---- Completion ----
echo ""
echo "Installation complete!"
echo "python3 /home/weston/imx93-ai-demo.py"
board_ip=$(ip route get 8.8.8.8 | awk '{for(i=1;i<=NF;i++){if($i=="src"){print $(i+1); exit}}}')
echo "Camera Live Stream url: https://$board_ip:8080/live"























# Force fresh install of SDK
python3 -m pip install --force-reinstall iotconnect-sdk-lite

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
