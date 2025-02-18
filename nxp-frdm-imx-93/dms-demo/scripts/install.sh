#!/bin/bash

echo "Updating environment variables..."
export PATH=$PATH:/usr/local/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib

echo "Creating Python virtual environment..."
python3 -m venv ~/iotconnect_env
source ~/iotconnect_env/bin/activate
pip install --upgrade pip
pip install flask numpy opencv-python requests iotconnect-sdk-lite

echo "Installing IoTConnect SDK..."
pip install iotconnect-sdk-lite

echo "Generating SSL certificates..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /home/weston/key.pem -out /home/weston/cert.pem -subj "/CN=localhost"

echo "Downloading IoTConnect Quickstart script..."
cd /home/weston/
curl -sSLo imx93-ai-demo.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/imx93-ai-demo.py"
chmod +x imx93-ai-demo.py

echo "Downloading DMS processing script..."
mkdir -p /usr/bin/eiq-examples-git/dms
curl -sSLo /usr/bin/eiq-examples-git/dms/dms-processing.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/dms-processing.py"
chmod +x /usr/bin/eiq-examples-git/dms/dms-processing.py

echo "Installation complete! You can now run the IoTConnect script:"
echo "python3 /home/weston/imx93-ai-demo.py"
