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
---- /IOTCONNECT Python Lite SDK QuickStart ----
This script will help guide through the setup of this device with /IOTCONNECT.
1. In the /IOTCONNECT Device view, click "Create Device" in the top-right corner
2. Enter "FRDMiMX93" for both Unique ID and Device Name
3. Select the only entity available in that the entity drop-down
4. Select the template "eiqIOTC" from the template drop-down
5. Change the Device Certificate to "Use my certificate"
6. Copy the certificate that will be printed below (including the BEGIN and END lines).
*** CAUTION: Do not use CTRL + C to copy at that will stop the script ***

END

read -rp "Press ENTER to display the certificate:"
echo
cat device-cert.pem

cat <<END
7. Return to the /IOTCONNECT platform and paste the certifcate below the "Certificate Text" box.
8. Click the "Save & View" button.
9. Click the "Paper and Cog" icon at top-right to download your device configuration file and save it to your working directory.
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

# ---- Download /IOTCONNECT QuickStart Script ----
echo "Downloading /IOTCONNECT QuickStart script..."
curl -sSL -o imx93-ai-demo.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/dms-demo/imx93-ai-demo.py" || {
    echo "Error: Failed to resolve host raw.githubusercontent.com. Please check your network and DNS settings."
    exit 1
}
chmod +x imx93-ai-demo.py

# ---- Download DMS Processing Script ----
echo "Downloading DMS processing script..."
curl -sSL -o /usr/bin/eiq-examples-git/dms/dms-processing.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/dms-demo/dms-processing.py" || {
    echo "Error: Failed to resolve host raw.githubusercontent.com. Please check your network and DNS settings."
    exit 1
}
chmod +x /usr/bin/eiq-examples-git/dms/dms-processing.py

# ---- Prompt User for eIQ AI Model Download ----
echo ""
read -p "Do you want to download eIQ AI Models? (y/n): " model_choice </dev/tty
echo "Download and process of models takes approximately 10 minutes"
if [[ "$model_choice" == "y" || "$model_choice" == "Y" ]]; then
    curl -sSL -o /usr/bin/eiq-examples-git/download_models.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/dms-demo/download_models.py" || {
        echo "Error: Failed to resolve host raw.githubusercontent.com. Please check your network and DNS settings."
        exit 1
        }
    chmod +x /usr/bin/eiq-examples-git/download_models.py 
    echo "Downloading eIQ AI Models..."
    python3 /usr/bin/eiq-examples-git/download_models.py
    
else
    echo "Skipping eIQ AI Models download."
fi

# Create empty dms-data.json with read/write perms
touch dms-data.json
chmod 666 dms-data.json

# ---- Completion ----
echo ""
echo "Installation complete! You can now run the /IOTCONNECT script:"
echo "python3 /home/weston/imx93-ai-demo.py"
board_ip=$(ip route get 8.8.8.8 | awk '{for(i=1;i<=NF;i++){if($i=="src"){print $(i+1); exit}}}')
echo "Camera Live Stream url: https://$board_ip:8080/live"
