#!/bin/sh

set -e

SITE_PACKAGES=$(python3 -c "import sys; print([p for p in sys.path if 'site-packages' in p][0])")

if [ -d "/root/iotc-python-lite-sdk/src/avnet" ]; then
    cp -r /root/iotc-python-lite-sdk/src/avnet $SITE_PACKAGES/
    echo "  - IoTConnect Lite SDK installed"
else
    echo "  - ERROR: SDK source not found!"
    exit 1
fi

if [ -d "/root/iotc-python-lib/src/avnet/iotconnect/sdk/sdklib" ]; then
    mkdir -p $SITE_PACKAGES/avnet/iotconnect/sdk/
    cp -r /root/iotc-python-lib/src/avnet/iotconnect/sdk/sdklib $SITE_PACKAGES/avnet/iotconnect/sdk/
    echo "  - sdklib installed"
else
    echo "  - ERROR: sdklib source not found!"
    exit 1
fi

cd ~
for wheel in *.whl; do
    if [ -f "$wheel" ]; then
        echo "  - Installing $wheel..."
        unzip -o "$wheel" -d $SITE_PACKAGES/ > /dev/null 2>&1
    fi
done
echo "  - All dependencies installed"
