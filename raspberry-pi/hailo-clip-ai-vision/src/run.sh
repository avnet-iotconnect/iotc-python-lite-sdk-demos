#!/bin/bash
# Launch the "Ask the Camera" demo (CLIP on Hailo-8 + /IOTCONNECT bridge).
# Usage: ./run.sh [--input /dev/video0] [extra hailo-clip args]
set -e
cd "$(dirname "$0")"
# one camera + one NPU: stop the Vision Multi-Tool if it is running
pkill -f "[H]ailo Detection App" 2>/dev/null || true
pkill -f "[H]ailo Pose" 2>/dev/null || true
pkill -f "[H]ailo Instance" 2>/dev/null || true
sleep 2
source ~/hailo-apps/setup_env.sh >/dev/null 2>&1 || true
export DISPLAY="${DISPLAY:-:0}" XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
exec ~/hailo-apps/venv_hailo_apps/bin/python3 hailo_iotc_bridge.py --input "${1:-/dev/video0}" "${@:2}"
