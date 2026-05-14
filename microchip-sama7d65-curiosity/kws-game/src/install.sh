#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

set -e

export PIP_ROOT_USER_ACTION=ignore

python_module_available() {
  python3 - "$1" <<'PY'
import importlib.util
import sys

module_name = sys.argv[1]
sys.exit(0 if importlib.util.find_spec(module_name) is not None else 1)
PY
}

if python3 -m pip install Flask iotconnect-sdk-lite requests; then
  echo "Verified Python package availability for Flask, iotconnect-sdk-lite, and requests."
else
  echo "WARNING: Unable to install Flask, iotconnect-sdk-lite, and requests automatically."
  echo "The app can still run if compatible versions are already present on the board."
fi

if python_module_available numpy; then
  echo "NumPy import: OK"
else
  echo "NumPy not found — installing from bundled package..."
  if [ -f "./numpy-bundle.tar.gz" ]; then
    tar -xzf ./numpy-bundle.tar.gz -C /
    ldconfig 2>/dev/null || true
    if python_module_available numpy; then
      echo "Installed NumPy from bundled package."
    else
      echo "WARNING: NumPy bundled install failed. Trying pip and opkg..."
      if python3 -m pip install --only-binary=:all: numpy; then
        echo "Installed NumPy from pip."
      elif opkg install python3-numpy 2>/dev/null; then
        echo "Installed NumPy via opkg."
      else
        echo "WARNING: Unable to install NumPy automatically."
        echo "Install a compatible wheel or pre-provision NumPy if this target image does not bundle it."
      fi
    fi
  else
    echo "WARNING: numpy-bundle.tar.gz not found."
    if python3 -m pip install --only-binary=:all: numpy; then
      echo "Installed NumPy from pip."
    elif opkg install python3-numpy 2>/dev/null; then
      echo "Installed NumPy via opkg."
    else
      echo "WARNING: Unable to install NumPy automatically."
    fi
  fi
fi

if python_module_available tflite_runtime; then
  echo "TensorFlow Lite interpreter import: OK (tflite_runtime)"
else
  if opkg install python3-tflite-runtime 2>/dev/null; then
    echo "Installed tflite-runtime via opkg."
  else
    echo "NOTE: tflite-runtime is not available for this platform via pip or opkg."
    echo "      The demo will use the bundled numpy-based TFLite interpreter instead."
    if python3 -m pip install --only-binary=:all: flatbuffers; then
      echo "Installed flatbuffers (required by numpy TFLite interpreter)."
    fi
  fi
fi

if command -v arecord >/dev/null 2>&1; then
  echo "Verified ALSA capture command: arecord"
else
  echo "WARNING: arecord is not available."
  echo "Install alsa-utils on the board if audio capture fails."
fi

mkdir -p /opt/demo/models

if [ -d "./models" ]; then
  SRC_MODELS=$(realpath "./models" 2>/dev/null || echo "")
  DST_MODELS=$(realpath "/opt/demo/models" 2>/dev/null || echo "none")
  if [ -n "$SRC_MODELS" ] && [ "$SRC_MODELS" != "$DST_MODELS" ]; then
    cp -f ./models/* /opt/demo/models/
    if [ -f "/opt/demo/models/model.tflite" ] && [ ! -f "/opt/demo/models/ds_cnn_s_quantized.tflite" ]; then
      cp -f /opt/demo/models/model.tflite /opt/demo/models/ds_cnn_s_quantized.tflite
    fi
    if [ -f "/opt/demo/models/ds_cnn_s_quantized.tflite" ] && [ ! -f "/opt/demo/models/model.tflite" ]; then
      cp -f /opt/demo/models/ds_cnn_s_quantized.tflite /opt/demo/models/model.tflite
    fi
  fi
  echo "Installed model assets into /opt/demo/models"
fi

python3 - <<'PY'
try:
    import numpy as np
    print(f"NumPy import: OK ({np.__version__})")
except Exception as exc:
    print(f"NumPy import: NOT AVAILABLE ({exc})")

try:
    from tflite_runtime.interpreter import Interpreter
    print("TensorFlow Lite interpreter import: OK (tflite_runtime)")
except Exception:
    try:
        import tensorflow as tf
        _ = tf.lite.Interpreter
        print("TensorFlow Lite interpreter import: OK (tensorflow)")
    except Exception:
        try:
            from tflite_numpy_interpreter import Interpreter
            print("TensorFlow Lite interpreter import: OK (numpy fallback)")
        except Exception as exc:
            print(f"TensorFlow Lite interpreter import: NOT AVAILABLE ({exc})")
PY

echo "KWS game install complete."
