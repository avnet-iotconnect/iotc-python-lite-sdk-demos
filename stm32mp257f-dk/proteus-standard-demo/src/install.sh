#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.

# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
# python3 -m pip install --force-reinstall iotconnect-sdk-lite
# ---------------------------------------------------------------------

dd if=/dev/zero of=/swapfile bs=1024 count=1048576
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo "Installing bleak python library, may take several minutes to complete."
pip3 install bleak
pip3 install blue_st_sdk-1.5.0-py3-none-any.whl
echo "Installation complete!"
