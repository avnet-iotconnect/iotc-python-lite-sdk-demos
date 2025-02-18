#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Nikola Markovic <nikola.markovic@avnet.com> et al.

set -e

# Workaround for Git bash failing with subject formatting error for OpenSSL
export MSYS_NO_PATHCONV=1

echo "Updating environment variables..."
export PATH=$PATH:/usr/local/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

use_curl=true

# ---- Functions ----

function check_sdk {
  if ! python3 -c 'from avnet.iotconnect.sdk.lite import Client' > /dev/null; then
    echo "The Python Lite SDK was not found. Please see instructions on how to install it at https://github.com/avnet-iotconnect/iotc-python-lite-sdk." >&2
  fi
}

function check_python_version {
  ver=$(python3 -c 'import sys; v=sys.version_info; print("%02d.%02d" % (v.major, v.minor))')
  if [[ ! "${ver}" < "03.09" ]]; then
    return 0
  else
    echo "Python version should be greater or equal to 3.9" >&2
    return 1
  fi
}

function has {
  if [ -z "$1" ]; then
    echo "Need argument 1" >&2
    exit 128
  fi
  if ! command -v "$1" &> /dev/null; then
    echo "Error: ${1} was not found. Please install it." >&2
    return 1
  fi
  return 0
}

function askyn {
  if [ -z "$1" ]; then
    echo "Need argument 1" >&2
    exit 128
  fi
  
  # Timeout & Default Answer (set to 'y' by default)
  DEFAULT_ANSWER="y"
  
  while true; do
    read -t 5 -rp "$1 [y/n]: " answer  # 5-second timeout for user input
    answer=${answer:-$DEFAULT_ANSWER}  # If empty, use default answer
    
    if [[ "${answer}" =~ ^[yY]$ ]]; then
      return 0
    elif [[ "${answer}" =~ ^[nN]$ ]]; then
      return 1
    else
      echo "Please answer 'y' or 'n'."
    fi
  done
}


function gencert {
  if [ -z "$1" ]; then
    echo "Need argument 1" >&2
    exit 128
  fi

  cn=$1
  subj="/C=US/ST=IL/L=Chicago/O=IoTConnect/CN=${cn}"
  days=36500 # 100 years
  ec_curve=prime256v1

  openssl ecparam -name ${ec_curve} -genkey -noout -out "${cn}-pkey.pem"
  openssl req -new -days ${days} -nodes -x509 \
      -subj "${subj}" -key "${cn}-pkey.pem" -out "${cn}-cert.pem"

  echo "X509 credentials are now generated as ${cn}-cert.pem and ${cn}-pkey.pem."
}

has python3 || exit 3
has openssl || exit 4

check_python_version || exit 5
check_sdk || exit 6

# ---- Install Dependencies ----
echo "Upgrading Pip..."
PIP_ROOT_USER_ACTION=ignore python3 -m pip install --upgrade pip  

echo "Installing dependencies..."
PIP_ROOT_USER_ACTION=ignore pip install --upgrade pip  
PIP_ROOT_USER_ACTION=ignore pip install flask numpy opencv-python requests iotconnect-sdk-lite

echo "Installing IoTConnect SDK..."
PIP_ROOT_USER_ACTION=ignore pip install iotconnect-sdk-lite  

# ---- Generate Certificates ----
if [[ -f "device-cert.pem" && -f "device-pkey.pem" ]]; then
  if askyn "It seems that the device certificate and key already exist. Do you want to overwrite them?"; then
    gencert "device"
  fi
else
  gencert "device"
fi

# ---- Download Quickstart Script ----# ---- IoTConnect Setup ----
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

read -rp "Press ENTER to print the certificate and proceed:"
cat device-cert.pem

# **Pause to allow copy-paste before continuing**
echo ""
echo "Copy the certificate above, then press ENTER to continue."
read -rp ""

cat <<END
- Click the "Save & View" button.
- Click the "Paper and Cog" icon at the top right to download your device configuration file.
Open the downloaded file in a text editor, paste the content into this terminal, and press ENTER after the last line.
END

# **Pause again before proceeding**
echo "Waiting for you to paste the configuration. Press ENTER when ready."
read -rp ""

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
cat <<END
Installation complete! You can now run the IoTConnect script:
python3 /home/weston/imx93-ai-demo.py
END
