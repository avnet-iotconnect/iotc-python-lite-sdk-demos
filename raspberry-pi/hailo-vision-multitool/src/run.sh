#!/bin/bash
# Launch the Hailo Vision Multi-Tool (detection/pose/segmentation + /IOTCONNECT).
# Supervises the bridge: pipeline teardown can segfault in native code on some
# mode switches, so a crash restarts the bridge into the last requested mode.
set -e
cd "$(dirname "$0")"
pkill -f "[H]ailo Python App" 2>/dev/null || true   # stop the CLIP demo if running
sleep 2
source ~/hailo-apps/setup_env.sh >/dev/null 2>&1 || true
export DISPLAY="${DISPLAY:-:0}" XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
while true; do
  ~/hailo-apps/venv_hailo_apps/bin/python3 -u hailo_vision_bridge.py "$@" && break
  code=$?
  echo "[supervisor] bridge exited with code $code — restarting into last requested mode"
  sleep 3
done
