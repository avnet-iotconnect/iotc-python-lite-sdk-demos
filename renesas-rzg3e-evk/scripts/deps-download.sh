#!/bin/bash

set -e  # Exit on any error

# Check if board IP is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <board-ip-address>"
    echo "Example: $0 192.168.1.100"
    exit 1
fi

BOARD_IP=$1
WORK_DIR="/tmp/iotc-packages"

echo ""
echo "Board IP: $BOARD_IP"
echo "Working directory: $WORK_DIR"
echo ""

mkdir -p $WORK_DIR
cd $WORK_DIR

if [ -d "iotc-python-lite-sdk" ]; then
    echo "  - Directory exists, pulling latest changes..."
    cd iotc-python-lite-sdk
    git pull
    cd ..
else
    git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk.git
fi

if [ -d "iotc-python-lib" ]; then
    echo "  - Directory exists, pulling latest changes..."
    cd iotc-python-lib
    git pull
    cd ..
else
    git clone https://github.com/avnet-iotconnect/iotc-python-lib.git
fi

pip3 download requests paho-mqtt -d $WORK_DIR

scp -r iotc-python-lite-sdk root@$BOARD_IP:~

scp -r iotc-python-lib root@$BOARD_IP:~

scp *.whl root@$BOARD_IP:~
