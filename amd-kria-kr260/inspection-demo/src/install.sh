#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

export PIP_ROOT_USER_ACTION=ignore

# Ubuntu 24.04 marks the system Python as externally managed (PEP 668).
# opencv-python-headless ships aarch64 wheels, so no apt packages or root
# privileges are needed; the whole demo runs unprivileged.
if ! python3 -m pip install --upgrade iotconnect-sdk-lite requests opencv-python-headless --break-system-packages; then
    echo "ERROR: dependency install failed; not marking installation complete." >&2
    exit 1
fi

echo "Installation complete!"
