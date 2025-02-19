#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Nikola Markovic <nikola.markovic@avnet.com> et al.

set -e  # Stop script on first failure

echo "BBB - Updating environment variables..."
export PATH=$PATH:/usr/local/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

# ---- Function for Wi-Fi Setup ----

setup_wifi() {
    echo "Scanning for available Wi-Fi networks..."
    connmanctl scan wifi >/dev/null 2>&1
    sleep 2  # Wait for scan to complete

    echo "Available Wi-Fi Networks:"
    connmanctl services | awk '{print NR")", $0}'

    read -p "Enter the number of the Wi-Fi network to connect to: " wifi_choice
    wifi_id=$(connmanctl services | awk "NR==$wifi_choice {print \$NF}")  # Extract full service ID

    echo "DEBUG: Selected Wi-Fi ID: '$wifi_id'"

    if [ -z "$wifi_id" ]; then
        echo "Invalid selection. Exiting Wi-Fi setup."
        return
    fi

    echo "Enter Wi-Fi passphrase (leave empty for open networks):"
    read -s wifi_passphrase

    echo "DEBUG: Connecting to Wi-Fi ID: '$wifi_id'"
    echo "Enabling Wi-Fi..."
    connmanctl enable wifi >/dev/null 2>&1

    echo "Starting ConnMan agent for authentication..."
    connmanctl agent on >/dev/null 2>&1

    echo "Connecting..."
    if [ -z "$wifi_passphrase" ]; then
        connmanctl connect "$wifi_id"
    else
        connmanctl connect "$wifi_id" <<< "$wifi_passphrase"
    fi

    if [[ $? -eq 0 ]]; then
        echo "Wi-Fi connected successfully!"
    else
        echo "Failed to connect to Wi-Fi. Please check credentials and try again."
        return
    fi

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
}


# ---- Prompt for Wi-Fi Setup ----
read -p "Do you want to set up Wi-Fi? (y/n): " wifi_choice
if [[ "$wifi_choice" == "y" || "$wifi_choice" == "Y" ]]; then
    setup_wifi
else
    echo "Skipping Wi-Fi setup."
fi

# ---- Upgrade Vela to Latest Version (Fixes Flatbuffers Conflict) ----
echo "Updating Vela Compiler..."
pip uninstall -y ethos-u-vela ethosu flatbuffers || true  # Remove old versions

# Install ethosu first to lock flatbuffers at 1.12.0
pip install --no-cache-dir flatbuffers==1.12.0 pybind11==2.8.1 ethosu

# Install ethos-u-vela WITHOUT dependencies to prevent flatbuffers upgrade
pip install --no-cache-dir --no-deps ethos-u-vela

# Verify final installation
echo "Vela updated to version: $(vela --version)"
pip show flatbuffers


# ---- Generate Certificates ----
echo "Generating SSL certificates..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout device-pkey.pem -out device-cert.pem -subj "/CN=localhost"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /usr/bin/eiq-examples-git/dms/key.pem -out /usr/bin/eiq-examples-git/dms/cert.pem -subj "/CN=localhost"
echo "X509 credentials are now generated."

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
- Open the downloaded file in a text editor, paste the content into this terminal, and press ENTER after the last line.
END

# **Pause and Wait for Configuration Paste**
echo ""
read -p "Paste your configuration below and press ENTER when done: " </dev/tty
echo "(Make sure to include the opening and closing curly brackets `{}`.)"
echo ""

# Create or overwrite the configuration file
> iotcDeviceConfig.json
while IFS= read -r line; do
  echo "$line" >> iotcDeviceConfig.json
  [[ $line == "}" ]] && break
done

echo ""
echo "Configuration file successfully saved."
read -p "Press ENTER to continue..."

# ---- Download IoTConnect Quickstart Script ----
echo "Downloading IoTConnect Quickstart script..."
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
    echo "Downloading eIQ AI Models..."
    cd /usr/bin/eiq-examples-git/
    if python3 download_models.py 2>/dev/null; then
        echo "eIQ AI Models downloaded successfully."
    else
        echo "⚠ Warning: There was an error downloading eIQ AI Models. Please verify the model URLs and file formats."
    fi
else
    echo "Skipping eIQ AI Models download."
fi

# ---- Completion ----
cd /home/weston
echo ""
echo "Installation complete! You can now run the IoTConnect script:"
echo "python3 /home/weston/imx93-ai-demo.py"
