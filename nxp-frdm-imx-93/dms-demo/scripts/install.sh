#!/bin/bash

echo "Updating environment variables..."
export PATH=$PATH:/usr/local/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

echo "Upgrading Pip..."
python3 -m pip install --upgrade pip  

echo "Installing dependencies..."
pip install --upgrade pip  
pip install flask numpy opencv-python requests iotconnect-sdk-lite

echo "Installing IoTConnect SDK..."
pip install iotconnect-sdk-lite  

echo "Generating SSL certificates..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048
