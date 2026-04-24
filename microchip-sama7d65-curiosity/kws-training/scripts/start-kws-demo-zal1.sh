#!/bin/sh
set -eu

/root/stop-kws-apps.sh >/dev/null 2>&1 || true

cd /root/kws-demo

export KWS_CONFIG_DIR=/root/zal1-config
export LD_LIBRARY_PATH=/root/kws-demo/libs
export KWS_MODEL_DIR=/opt/demo/models
export KWS_ARECORD_DEVICE="${KWS_ARECORD_DEVICE:-plughw:0,0}"
export KWS_DETECTION_THRESHOLD="${KWS_DETECTION_THRESHOLD:-0.80}"
export KWS_MIN_SIGNAL_RMS="${KWS_MIN_SIGNAL_RMS:-0.015}"
export KWS_COOLDOWN_SECS="${KWS_COOLDOWN_SECS:-1.0}"
export KWS_TELEMETRY_SECS="${KWS_TELEMETRY_SECS:-15}"

echo "Starting kws-demo in foreground as ZaL1"
echo "Stop with Ctrl+C"

exec /root/kws-venv/bin/python -u /root/kws-demo/kws_demo.py
