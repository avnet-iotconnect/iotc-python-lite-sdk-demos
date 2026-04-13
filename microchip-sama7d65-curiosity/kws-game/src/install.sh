#!/bin/bash
set -e

export PIP_ROOT_USER_ACTION=ignore

if python3 -m pip install Flask; then
  echo "Verified Flask availability."
else
  echo "WARNING: Unable to install Flask automatically."
fi

mkdir -p ./models
echo "KWS game install complete."
