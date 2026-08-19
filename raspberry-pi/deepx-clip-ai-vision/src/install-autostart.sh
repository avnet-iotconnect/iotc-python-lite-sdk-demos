#!/bin/bash
# Install (or remove) the desktop autostart entry for the CLIP demo.
# Run this ON THE BOARD:  ~/deepx/dx_clip_demo/bridge/install-autostart.sh [--remove]
set -e
DEST="$HOME/.config/autostart/clip-demo.desktop"
if [ "$1" = "--remove" ]; then
    rm -f "$DEST"
    echo "Autostart removed."
    exit 0
fi
mkdir -p "$(dirname "$DEST")"
cp "$(dirname "$0")/clip-demo.desktop" "$DEST"
echo "Autostart installed -> $DEST"
echo "The demo launches in a terminal ~10 s after the desktop appears on every boot."
echo "Requires desktop auto-login (raspi-config -> System Options -> Boot / Auto Login -> Desktop Autologin)."
