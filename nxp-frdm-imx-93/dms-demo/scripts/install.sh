#!/bin/bash

echo "Updating package lists and installing required dependencies..."
sudo apt update && sudo apt upgrade -y

# Fix missing repository issue for libssl-dev (ensure universe repo is enabled)
sudo apt install -y software-properties-common
sudo add-apt-repository universe -y
sudo apt update

# Install required packages
sudo apt install -y \
    git \
    curl \
    wget \
    unzip \
    python3 \
    python3-pip \
    python3-venv \
    openssl \
    libopencv-dev \
    libffi-dev \
    libssl-dev \
    libcurl4-openssl-dev || { echo "Package installation failed. Exiting."; exit 1; }

echo "Creating Python virtual environment..."
python3 -m venv ~/iotconnect_env
source ~/iotconnect_env/bin/activate
pip install --upgrade pip
pip install flask numpy opencv-python requests fcntl json avnet-iotconnect-sdk-lite

echo "Installing IoTConnect SDK..."
pip install iotconnect-sdk-lite

echo "Generating SSL certificates..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /home/weston/key.pem -out /home/weston/cert.pem -subj "/CN=localhost"

echo "Downloading IoTConnect Quickstart script..."
cd /home/weston/
wget -O imx93-ai-demo.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/imx93-ai-demo.py"
chmod +x imx93-ai-demo.py

echo "Downloading DMS processing script..."
mkdir -p /usr/bin/eiq-examples-git/dms
wget -O /usr/bin/eiq-examples-git/dms/dms-processing.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/dms-processing.py"
chmod +x /usr/bin/eiq-examples-git/dms/dms-processing.py

echo "Installation complete! You can now run the IoTConnect script:"
echo "python3 /home/weston/imx93-ai-demo.py"
