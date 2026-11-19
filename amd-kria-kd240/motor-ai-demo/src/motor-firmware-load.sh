#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
#
# Ensure the kd240-motor-ctrl-qei PL firmware is loaded. Idempotent; run as
# root (systemd ExecStartPre). Waits for the dfx-mgr daemon after boot.

for _ in $(seq 1 30); do
    xmutil listapps >/dev/null 2>&1 && break
    sleep 2
done

if xmutil listapps 2>/dev/null | awk '$1 == "kd240-motor-ctrl-qei" && $NF ~ /->/ { found = 1 } END { exit !found }'; then
    echo "Motor-control firmware already loaded"
    exit 0
fi

xmutil unloadapp >/dev/null 2>&1 || true
exec xmutil loadapp kd240-motor-ctrl-qei
