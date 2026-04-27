#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

export PIP_ROOT_USER_ACTION=ignore

python3 -m pip install --upgrade iotconnect-sdk-lite requests

echo "Installation complete!"
