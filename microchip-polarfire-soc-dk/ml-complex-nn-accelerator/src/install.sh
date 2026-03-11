#!/bin/sh
set -eu

python3 -m pip install --upgrade iotconnect-sdk-lite requests

# Make runtimes executable when present.
if [ -d "./runtimes" ]; then
  chmod +x ./runtimes/*.elf 2>/dev/null || true
fi

echo "Install complete."
