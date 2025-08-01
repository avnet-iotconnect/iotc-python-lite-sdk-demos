#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
# python3 -m pip install --force-reinstall iotconnect-sdk-lite
# ---------------------------------------------------------------------

pip3 install dbus_fast-2.44.1-cp312-cp312-manylinux_2_39_armv7l.whl
pip3 install bleak
echo "Installation complete!"
