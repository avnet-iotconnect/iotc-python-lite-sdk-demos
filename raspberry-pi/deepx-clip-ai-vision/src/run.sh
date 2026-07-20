#!/bin/bash
# Launch the "Ask the Camera" demo (CLIP on DX-M1 + /IOTCONNECT bridge).
# Usage: ./run.sh [camera-index]   (default camera 0)
set -e
cd "$(dirname "$0")/.."
source venv-opencv/bin/activate
exec python bridge/dx_iotc_bridge.py --camera "${1:-0}"
