#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Nikola Markovic <nikola.markovic@avnet.com> et al.

set -e  # Stop script on first failure

echo "Updating environment variables..."
export PATH=$PATH:/usr/local/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

# Define askyn function if not defined
askyn() {
    read -rp "$1 (y/n): " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

echo "Installing dependencies..."
PIP_ROOT_USER_ACTION=ignore python3 -m pip install flask numpy opencv-python requests filelock networkx

echo "Installing /IOTCONNECT SDK..."
PIP_ROOT_USER_ACTION=ignore python3 -m pip install iotconnect-sdk-lite  

# ---- Generate Certificates ----
echo "Generating SSL certificates..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout device-pkey.pem -out device-cert.pem -subj "/CN=localhost"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /usr/bin/eiq-examples-git/dms/key.pem -out /usr/bin/eiq-examples-git/dms/cert.pem -subj "/CN=localhost"
echo "X509 credentials are now generated."

cat <<END
---- IoTconnect Python Lite SDK Quickstart ----
This script will help guide you through the setup of this device with IoTConnect.
Ensure that you have read the guide at https://github.com/avnet-iotconnect/iotc-python-lite-sdk on how to install the lite SDK before proceeding.
If you are already familiar with IoTConnect you can follow these simple steps:
- Create the device template by uploading TBD link to template.
- Create a new device and:
  - Select your Entity and the newly created template.
  - Click the "Use my certificate" radio button.
  - Copy and paste the certificate that will be printed, including the BEGIN and END lines into the Certificate Text field:
END

read -rp "ENTER to print the certificate and proceed:"
echo 
cat device-cert.pem

cat <<END
- Click the "Save & View" button.
- Click the "Paper and Cog" icon at top right to download your device configuration file.
END

paste_config_json=true
if [[ -f "iotcDeviceConfig.json" ]]; then
  if ! askyn "It seems that the iotcDeviceConfig.json already exists. Do you want to overwrite it?"; then
    paste_config_json=false
  fi
fi

if ${paste_config_json}; then
  echo "Open the downloaded file in a text editor and paste the content into this terminal and press ENTER to add the last line:"
  echo > iotcDeviceConfig.json
  while true; do
    read -r line
    echo "${line}" >> iotcDeviceConfig.json
    if [[ "${line}" == "}" ]]; then
      break
    fi
  done
fi

# ---- Download /IOTCONNECT Quickstart Script ----
echo "Downloading /IOTCONNECT Quickstart script..."
    cd /home/weston/
curl -sSL -o imx93-ai-demo.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/dms-demo/imx93-ai-demo.py" || {
    echo "Error: Failed to resolve host raw.githubusercontent.com. Please check your network and DNS settings."
    exit 1
}
chmod +x imx93-ai-demo.py

# ---- Download DMS Processing Script ----
echo "Downloading DMS processing script..."
curl -sSL -o /usr/bin/eiq-examples-git/dms/dms-processing-final.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/dms-demo/dms-processing.py" || {
    echo "Error: Failed to resolve host raw.githubusercontent.com. Please check your network and DNS settings."
    exit 1
}
chmod +x /usr/bin/eiq-examples-git/dms/dms-processing-final.py

# ---- Prompt User for eIQ AI Model Download ----
echo ""
read -p "Do you want to download eIQ AI Models? (y/n): " model_choice </dev/tty
if [[ "$model_choice" == "y" || "$model_choice" == "Y" ]]; then
    cd /usr/bin/eiq-examples-git/
    curl -sSL -o download_models.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/dms-demo/download_models.py" || {
        echo "Error: Failed to resolve host raw.githubusercontent.com. Please check your network and DNS settings."
        exit 1
    }
    chmod +x download_models.py
    echo "Downloading eIQ AI Models..."
    if python3 download_models.py 2>/dev/null; then
        echo "eIQ AI Models downloaded successfully."
    else
        echo "Warning: There was an error downloading eIQ AI Models. Please verify the model URLs and file formats."
    fi
else
    echo "Skipping eIQ AI Models download."
fi

# ---- Completion ----
cd /home/weston
echo ""
echo "Installation complete! You can now run the /IOTCONNECT script:"
echo "python3 /home/weston/imx93-ai-demo.py"
board_ip=$(ip route get 8.8.8.8 | awk '{for(i=1;i<=NF;i++){if($i=="src"){print $(i+1); exit}}}')
echo "Camera Live Stream url: https://$board_ip:8080/live"
