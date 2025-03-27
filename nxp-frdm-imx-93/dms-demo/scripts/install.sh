#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

PIP_ROOT_USER_ACTION=ignore python3 -m pip install flask numpy opencv-python requests filelock networkx

cp ./download_models.py /usr/bin/eiq-examples-git

cd /usr/bin/eiq-examples-git

python3 download_models.py

cd /home/weston/demo

# Create empty dms-data.json with read/write perms
touch dms-data.json
chmod 666 dms-data.json

cp /usr/bin/eiq-examples-git/dms/face_detection.py .
cp /usr/bin/eiq-examples-git/dms/eye_landmark.py .
cp /usr/bin/eiq-examples-git/dms/face_landmark.py .
cp /usr/bin/eiq-examples-git/dms/utils.py .

# Find and copy all .tflite files in the current directory to the models directory
DEST_DIR="/usr/bin/eiq-examples-git/models"
for file in *.tflite; do
  if [ -f "$file" ]; then
    echo "Moving $file to $DEST_DIR"
    cp "$file" "$DEST_DIR"
  fi
done

# Run python script that uses the API to delete the existing device and then create a new one with the same name but with the i.MX 93 template

echo "Installation complete!"
board_ip=$(ip route get 8.8.8.8 | awk '{for(i=1;i<=NF;i++){if($i=="src"){print $(i+1); exit}}}')
echo "Camera Live Stream url: https://$board_ip:8080/live"
