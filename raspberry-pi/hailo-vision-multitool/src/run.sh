#!/bin/bash
# Launch the Hailo Vision Multi-Tool (detection/pose/segmentation + /IOTCONNECT).
# Stops the CLIP demo first (one camera + one NPU per demo).
set -e
cd "$(dirname "$0")"
pkill -f "[H]ailo Python App" 2>/dev/null || true
sleep 2
source ~/hailo-apps/setup_env.sh >/dev/null 2>&1 || true
export DISPLAY="${DISPLAY:-:0}" XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
exec ~/hailo-apps/venv_hailo_apps/bin/python3 hailo_vision_bridge.py "$@"
