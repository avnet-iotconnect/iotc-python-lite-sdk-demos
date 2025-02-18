#!/bin/bash
echo "Installing dependencies..."
sudo apt update && sudo apt install -y git curl unzip python3-pip python3-venv

echo "Creating Python virtual environment..."
python3 -m venv ~/iotconnect_env
source ~/iotconnect_env/bin/activate
pip install --upgrade pip
pip install flask numpy opencv-python requests fcntl json fcntl avnet-iotconnect-sdk-lite

echo "Installing IoTConnect SDK..."
pip install iotconnect-sdk-lite

echo "Generating SSL certificates..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /home/weston/key.pem -out /home/weston/cert.pem -subj "/CN=localhost"

echo "Installation complete!"

