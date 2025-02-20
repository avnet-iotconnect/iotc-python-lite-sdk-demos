#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Nikola Markovic <nikola.markovic@avnet.com> et al.

set -e  # Stop script on first failure

echo "666-Updating environment variables..."
export PATH=$PATH:/usr/local/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

# ---- Function for Wi-Fi Setup ----

setup_wifi() {
    # Load the Wi-Fi module with parameters
    modprobe moal mod_para=/lib/firmware/nxp/wifi_mod_para.conf
    # Make Wi-Fi persistent across reboots
    echo "Making Wi-Fi persistent..."
    echo "moal mod_para=nxp/wifi_mod_para.conf" > /etc/modules-load.d/moal.conf
    echo "options moal mod_para=nxp/wifi_mod_para.conf" > /etc/modprobe.d/moal.conf
    cat <<EOF | tee /etc/systemd/system/wifi-setup.service >/dev/null
[Unit]
Description=WiFi Setup
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/modprobe moal mod_para=/lib/firmware/nxp/wifi_mod_para.conf
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable wifi-setup.service
    systemctl start wifi-setup.service

    echo "Wi-Fi setup is now permanent!"
    echo "Enabling Wi-Fi..."
    connmanctl enable wifi
    sleep 1

    echo "Scanning for available Wi-Fi networks..."
    connmanctl scan wifi
    sleep 4  # Wait for scan to complete

    # Capture the list of available Wi-Fi networks
    wifi_list=$(connmanctl services)
    sleep 2

    # Check if any networks were found
    if [ -z "$wifi_list" ]; then
        echo "No Wi-Fi networks found. Exiting Wi-Fi setup."
        return 1
    fi

    echo "Available Wi-Fi Networks:"
    echo "$wifi_list" | awk '{print NR")", $0}'

    read -p "Enter the number of the Wi-Fi network to connect to: " wifi_choice
    # Check if input is empty
    if [ -z "$wifi_choice" ]; then
        echo "No network selected. Exiting Wi-Fi setup."
        return 1
    fi

    # Extract the Wi-Fi service ID from the stored list using the selected line number
    wifi_id=$(echo "$wifi_list" | awk "NR==$wifi_choice {print \$NF}")

    echo "Selected Wi-Fi ID: '$wifi_id'"

    if [ -z "$wifi_id" ]; then
        echo "Invalid selection. Exiting Wi-Fi setup."
        return 1
    fi

    echo "Enter Wi-Fi passphrase (leave empty for open networks):"
    read -s wifi_passphrase

    echo "Connecting to Wi-Fi ID: '$wifi_id'"
    echo "Connecting..."
    if [ -z "$wifi_passphrase" ]; then
        echo "Starting ConnMan agent for authentication..."
( expect <<'EOF'
spawn connmanctl
expect "connmanctl>"
send "agent on\r"
expect "Agent registered"
connect ""$wifi_id"\r"
# Keep the agent running so it remains active for connections.
sleep 5
EOF
) &
    else
( expect <<'EOF'
spawn connmanctl
expect "connmanctl>"
send "agent on\r"
expect "Agent registered"
connect ""$wifi_id" <<< "$wifi_passphrase"\r"
# Keep the agent running so it remains active for connections.
sleep 5
EOF
) &
    fi

    if [[ $? -eq 0 ]]; then
        echo "Wi-Fi connected successfully!"
    else
        echo "Failed to connect to Wi-Fi. Please check credentials and try again."
        return 1
    fi
}


# ---- Prompt for Wi-Fi Setup ----
read -p "Do you want to set up Wi-Fi? (y/n): " wifi_choice_input
if [[ "$wifi_choice_input" == "y" || "$wifi_choice_input" == "Y" ]]; then
    setup_wifi
else
    echo "Skipping Wi-Fi setup."
fi

#echo "Upgrading Pip..."
#PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade pip  

echo "Installing dependencies..."
#PIP_ROOT_USER_ACTION=ignore pip install --upgrade pip  
PIP_ROOT_USER_ACTION=ignore python3 -m pip install flask numpy opencv-python requests filelock networkx

echo "Installing /IOTCONNECT SDK..."
PIP_ROOT_USER_ACTION=ignore python3 -m pip install iotconnect-sdk-lite  

# ---- Upgrade Vela to Latest Version (Fixes Flatbuffers Conflict) ----
#echo "Updating Vela Compiler..."

# Uninstall conflicting versions
#python3 -m pip uninstall -y ethos-u-vela flatbuffers || true

# Find a compatible Flatbuffers version (>=2.0.0 but NOT 1.12.0)
#python3 -m pip install --force-reinstall flatbuffers==1.12.0
#python3 -m pip install --no-cache-dir "flatbuffers>=2.0.0,<3.0.0" pybind11==2.8.1  

# Install ethos-u-vela without dependencies to prevent flatbuffers upgrade
#python3 -m pip install --no-cache-dir --no-deps ethos-u-vela

# Verify final installation
#echo "Vela updated to version: $(vela --version)"
#python3 -m pip show flatbuffers


# ---- Generate Certificates ----
echo "Generating SSL certificates..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout device-pkey.pem -out device-cert.pem -subj "/CN=localhost"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /usr/bin/eiq-examples-git/dms/key.pem -out /usr/bin/eiq-examples-git/dms/cert.pem -subj "/CN=localhost"
echo "X509 credentials are now generated."

cat <<END
---- IoTconnect Python Lite SDK Quickstart ----
This script will help guide you through the setup this device with IoTConnect.
Ensure that you have read the guide at https://github.com/avnet-iotconnect/iotc-python-lite-sdk on how to install the lite SDK before proceeding.
If you are already familiar with IoTconnect you can follow these simple steps:
- Create the device template by uploading TBD link to template.
- Create a new device and:
  - Select your Entity and the newly created template.
  - Click the "Use my certificate" radio button.
  - Copy and paste the certificate that will be printed, including the BEGIN and END lines into the Certificate Text field:
END

read -rp "ENTER to print the certificate and proceed:"
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

if ${paste_config_json} ]]; then
  echo "Open the downloaded file in a text editor and paste the content into this terminal and press ENTER to add the last line:"

  echo > iotcDeviceConfig.json
  while true; do
    read -r line
    echo "${line}" >> iotcDeviceConfig.json
    if [[ "${line}" == "}" ]]; then
      break
    fi
  done

fi # paste_config_json

# ---- Download /IOTCONNECT Quickstart Script ----
echo "Downloading /IOTCONNECT Quickstart script..."
cd /home/weston/
curl -sSLo imx93-ai-demo.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/imx93-ai-demo.py"
chmod +x imx93-ai-demo.py

# ---- Download DMS Processing Script ----
echo "Downloading DMS processing script..."
curl -sSLo /usr/bin/eiq-examples-git/dms/dms-processing-final.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/dms-processing.py"
chmod +x /usr/bin/eiq-examples-git/dms/dms-processing-final.py

# ---- Prompt User for eIQ AI Model Download ----
echo ""
read -p "Do you want to download eIQ AI Models? (y/n): " model_choice </dev/tty
if [[ "$model_choice" == "y" || "$model_choice" == "Y" ]]; then
    cd /usr/bin/eiq-examples-git/
    curl -sSLo /usr/bin/eiq-examples-git/download_models.py "https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/mcl-DMS-updates/nxp-frdm-imx-93/dms-demo/download_models.py"
    chmod +x /usr/bin/eiq-examples-git/download_models.py
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

