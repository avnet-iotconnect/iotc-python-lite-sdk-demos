#!/bin/bash
# Capture HSV thresholds for the colored ball used by the ball-follow mode.
# Writes ball_color.json next to this script.
#
# Defaults to the browser-based calibrator (RZ/G3E has no display server,
# and we install opencv-python-headless so cv2.imshow won't render). Open
# http://<board-ip>:8000/ from any PC on the same LAN once it's running.
# Use BROWSER=0 to fall back to the original cv2-window calibrator.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "${BROWSER:-1}" = "0" ]; then
    exec python3 -u ball_calibrate.py "$@"
else
    exec python3 -u browser_calibrate.py "$@"
fi
