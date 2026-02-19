#!/bin/bash
set -euo pipefail

python3 -m pip install --upgrade iotconnect-sdk-lite requests

if compgen -G "./runtimes/*.elf" > /dev/null; then
  chmod +x ./runtimes/*.elf
fi

echo "Install complete."
