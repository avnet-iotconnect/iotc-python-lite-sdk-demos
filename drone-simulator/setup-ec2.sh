#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
#
# Installs the /IOTCONNECT drone simulator on an EC2 instance (Amazon Linux 2023 or Ubuntu)
# as a systemd service that starts on boot.
#
# Usage (run from the drone-simulator directory as a user with sudo):
#   bash ./setup-ec2.sh /path/to/iotcDeviceConfig.json /path/to/cert_drone1.crt /path/to/pk_drone1.pem
#
# Optional environment overrides:
#   INSTALL_DIR=/opt/drone-simulator   Where the app and credentials are installed
#   NORMAL_INTERVAL_SECS=90            Telemetry period outside demo mode
#   DEMO_INTERVAL_SECS=3               Telemetry period in demo mode
#   DEMO_DURATION_MINUTES=5            Default demo length when the command has no argument

set -euo pipefail

CONFIG_SRC="${1:-}"
CERT_SRC="${2:-}"
KEY_SRC="${3:-}"
INSTALL_DIR="${INSTALL_DIR:-/opt/drone-simulator}"
SERVICE_NAME="drone-simulator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${CONFIG_SRC}" || -z "${CERT_SRC}" || -z "${KEY_SRC}" ]]; then
  echo "Usage: $0 <iotcDeviceConfig.json> <device certificate> <device private key>" >&2
  exit 1
fi
for f in "${CONFIG_SRC}" "${CERT_SRC}" "${KEY_SRC}"; do
  if [[ ! -f "${f}" ]]; then
    echo "File not found: ${f}" >&2
    exit 1
  fi
done

SUDO=""
if [[ "$(id -u)" -ne 0 ]]; then
  SUDO="sudo"
fi

echo "==> Installing system packages"
if command -v dnf >/dev/null 2>&1; then
  ${SUDO} dnf install -y -q python3 python3-pip
elif command -v apt-get >/dev/null 2>&1; then
  ${SUDO} apt-get update -qq
  ${SUDO} apt-get install -y -qq python3 python3-pip python3-venv
else
  echo "Unsupported package manager. Install python3 (>= 3.9) and pip manually, then re-run." >&2
  exit 1
fi

echo "==> Creating ${INSTALL_DIR}"
${SUDO} mkdir -p "${INSTALL_DIR}"
${SUDO} cp "${SCRIPT_DIR}/src/app.py" "${INSTALL_DIR}/app.py"
${SUDO} cp "${CONFIG_SRC}" "${INSTALL_DIR}/iotcDeviceConfig.json"
${SUDO} cp "${CERT_SRC}" "${INSTALL_DIR}/device-cert.pem"
${SUDO} cp "${KEY_SRC}" "${INSTALL_DIR}/device-pkey.pem"
${SUDO} chmod 600 "${INSTALL_DIR}/device-pkey.pem"

echo "==> Creating Python virtual environment and installing the /IOTCONNECT Python Lite SDK"
${SUDO} python3 -m venv "${INSTALL_DIR}/venv"
${SUDO} "${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
${SUDO} "${INSTALL_DIR}/venv/bin/pip" install --quiet iotconnect-sdk-lite

echo "==> Writing service environment"
${SUDO} tee "${INSTALL_DIR}/simulator.env" >/dev/null <<EOF
NORMAL_INTERVAL_SECS=${NORMAL_INTERVAL_SECS:-90}
DEMO_INTERVAL_SECS=${DEMO_INTERVAL_SECS:-3}
DEMO_DURATION_MINUTES=${DEMO_DURATION_MINUTES:-5}
EOF

echo "==> Installing systemd service ${SERVICE_NAME}"
sed "s#@INSTALL_DIR@#${INSTALL_DIR}#g" "${SCRIPT_DIR}/drone-simulator.service" | ${SUDO} tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null
${SUDO} systemctl daemon-reload
${SUDO} systemctl enable "${SERVICE_NAME}"
${SUDO} systemctl restart "${SERVICE_NAME}"

cat <<EOF

Installation complete. The simulator is running as the '${SERVICE_NAME}' service.

  Follow the log:     sudo journalctl -u ${SERVICE_NAME} -f
  Restart:            sudo systemctl restart ${SERVICE_NAME}
  Stop:               sudo systemctl stop ${SERVICE_NAME}
  Change intervals:   edit ${INSTALL_DIR}/simulator.env and restart the service
EOF
