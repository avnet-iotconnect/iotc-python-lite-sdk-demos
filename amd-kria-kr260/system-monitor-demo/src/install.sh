#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

export PIP_ROOT_USER_ACTION=ignore

# Ubuntu 24.04 marks the system Python as externally managed (PEP 668).
if ! python3 -m pip install --upgrade iotconnect-sdk-lite requests --break-system-packages; then
    echo "ERROR: dependency install failed; not marking installation complete." >&2
    exit 1
fi

# The list-apps/load-app/unload-app cloud commands shell out to xmutil, which
# requires root. Install a sudoers rule that lets the demo user run exactly
# the invocations the app issues (each wrapped in a root-owned timeout so a
# wedged xmutil cannot hang the app) without a password. Best effort: during
# OTA (app.py sets IOTC_OTA=1 and detaches stdin) sudo is never allowed to
# prompt, and a failure only prints the manual instructions.
DEMO_USER="${SUDO_USER:-$(id -un)}"
RULE="$DEMO_USER ALL=(root) NOPASSWD: /usr/bin/timeout -k 5 115 /usr/bin/xmutil listapps, /usr/bin/timeout -k 5 115 /usr/bin/xmutil unloadapp, /usr/bin/timeout -k 5 115 /usr/bin/xmutil loadapp *"

# Functional probe: /etc/sudoers.d is not readable by the demo user, so test
# the rule by running the exact wrapped command with the sudo timestamp
# cleared (sudo -k) so a cached password cannot fake a pass.
xmutil_rule_works() {
    sudo -k 2>/dev/null
    sudo -n /usr/bin/timeout -k 5 115 /usr/bin/xmutil listapps >/dev/null 2>&1
}

if [ "$DEMO_USER" != "root" ] && ! xmutil_rule_works; then
    SUDO="sudo -n"
    if [ -t 0 ] && [ "${IOTC_OTA:-0}" != "1" ]; then
        SUDO="sudo"
    fi
    printf '%s\n' "$RULE" | $SUDO tee /etc/sudoers.d/99-iotc-xmutil >/dev/null 2>&1 \
        && $SUDO chmod 0440 /etc/sudoers.d/99-iotc-xmutil 2>/dev/null
    if xmutil_rule_works; then
        echo "Installed sudoers rule for $DEMO_USER (xmutil app management)."
    else
        echo "WARNING: the xmutil sudoers rule is not working."
        echo "The list-apps/load-app/unload-app commands will fail until you run this"
        echo "once from an interactive shell on the board:"
        echo "  cd /opt/demo && bash ./install.sh"
    fi
fi

echo "Installation complete!"
