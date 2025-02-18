#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Nikola Markovic <nikola.markovic@avnet.com> et al.

set -e

echo "Updating environment variables..."
export PATH=$PATH:/usr/local/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

echo "Upgrading Pip..."
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade pip  

echo "Installing dependencies..."
PIP_ROOT_USER_ACTION=ignore pip install --upgrade pip  
PIP_ROOT_USER_ACTION=ignore pip install flask numpy opencv-python requests iotconnect-sdk-lite

echo "Installing IoTConnect SDK..."
PIP_ROOT_USER_ACTION=ignore pip install iotconnect-sdk-lite  

# ---- Generate Certificates ----
echo "Generating SSL certificates..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout device-pkey.pem -out device-cert.pem -subj "/CN=localhost"

echo "X509 credentials are now generated as device-cert.pem and device-pkey.pem."

# ---- IoTConnect Setup ----
cat <<END
---- IoTConnect Python Lite SDK Quickstart ----
This script will help guide you through setting up this device with IoTConnect.
Ensure that you have read the guide at https://github.com/avnet-iotconnect/iotc-python-lite-sdk on how to install the Lite SDK before proceeding.

Follow these steps:
- Create the device template by uploading TBD link to template.
- Create a new device and:
  - Select your Entity and the newly created template.
  - Click the "Use my certificate" radio button.
  - Copy and paste the certificate that will be printed, including the BEGIN and END lines into the Certificate Text field:
END

# **Pause for Copying the Certificate**
echo ""
cat device-cert.pem
echo ""
read -p "Copy the certificate above, then press ENTER to continue."

cat <<END
- Click the "Save & View" button.
- Click the "Paper and Cog" icon at the top right to download your device configuration file.
Open the downloaded file in a text editor, paste the content into this terminal, and press ENTER after the last line.
END

# **Pause for Pasting Configuration File**
echo ""
read -p "Waiting for you to paste the configuration. Press ENTER when ready."

# ---- Download IoTConnect Quickstart Script ----
echo "Downloading IoTConnect Quickstart script..."
cd /home/weston/
curl -sSLo imx93-ai-demo.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/imx93-ai-demo.py"
chmod +x imx93-ai-demo.py

# ---- Download DMS Processing Script ----
echo "Downloading DMS processing script..."
mkdir -p /usr/bin/eiq-examples-git/dms
curl -sSLo /usr/bin/eiq-examples-git/dms/dms-processing.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/dms-processing.py"
chmod +x /usr/bin/eiq-examples-git/dms/dms-processing.py

# ---- Completion ----
echo ""
echo "Installation complete! You can now run the IoTConnect script:"
echo "python3 /home/weston/imx93-ai-demo.py"
