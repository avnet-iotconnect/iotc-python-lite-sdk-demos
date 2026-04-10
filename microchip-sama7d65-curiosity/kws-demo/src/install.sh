#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

set -e

export PIP_ROOT_USER_ACTION=ignore

python3 -m pip install --upgrade iotconnect-sdk-lite requests numpy

if python3 -m pip install --upgrade tflite-runtime; then
  echo "Installed tflite-runtime from pip."
else
  echo "WARNING: Unable to install tflite-runtime from pip."
  echo "The app can still run if a compatible TensorFlow Lite interpreter is already present."
fi

if command -v arecord >/dev/null 2>&1; then
  echo "Verified ALSA capture command: arecord"
else
  echo "WARNING: arecord is not available."
  echo "Install alsa-utils on the board if audio capture fails."
fi

mkdir -p /opt/demo/models

if [ -d "./models" ] && [ ! -f "/opt/demo/models/ds_cnn_s_quantized.tflite" ]; then
  cp -f ./models/* /opt/demo/models/
  echo "Installed model assets into /opt/demo/models"
elif [ -f "/opt/demo/models/ds_cnn_s_quantized.tflite" ]; then
  echo "Bundled model assets already present in /opt/demo/models"
fi

python3 - <<'PY'
try:
    from tflite_runtime.interpreter import Interpreter
    print("TensorFlow Lite interpreter import: OK (tflite_runtime)")
except Exception:
    try:
        import tensorflow as tf
        _ = tf.lite.Interpreter
        print("TensorFlow Lite interpreter import: OK (tensorflow)")
    except Exception as exc:
        print(f"TensorFlow Lite interpreter import: NOT AVAILABLE ({exc})")
PY

echo "Installation complete."
