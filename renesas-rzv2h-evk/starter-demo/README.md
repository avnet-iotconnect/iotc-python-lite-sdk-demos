# RZ/V2H EVK — Starter Demo

This demo connects the Renesas RZ/V2H EVK to /IOTCONNECT and streams real-time system
performance telemetry: CPU utilisation, RAM usage, and CPU temperatures read directly
from the Linux kernel's `/proc` and `/sys` interfaces. No additional packages beyond the
IoTConnect SDK are required.

## Setup

1. Complete the [board setup and device onboarding](../README.md) in the main guide.
2. Import `rzv2h-starter-template.json` as the device template in /IOTCONNECT.
3. Place your credential files in `/opt/demo`:
   - `iotcDeviceConfig.json`
   - `device-cert.pem`
   - `device-pkey.pem`

## Deploy

### Option A — Copy source directly

```bash
cd /opt/demo
scp user@host:.../renesas-rzv2h-evk/starter-demo/src/* .
bash install.sh && rm install.sh
```

### Option B — OTA package

Build the package on your host:

```bash
cd renesas-rzv2h-evk/starter-demo
bash create-package.sh
```

Then send a `file-download` command from /IOTCONNECT pointing to a hosted `package.tar.gz`.

## Run

```bash
cd /opt/demo
python3 app.py
```

## Telemetry

| Attribute | Type | Description |
|-----------|------|-------------|
| `sdk_version` | STRING | IoTConnect SDK version |
| `cpu_percent` | DECIMAL | CPU utilisation (%) |
| `memory_percent` | DECIMAL | RAM usage (%) |
| `cpu_temp_0_c` | DECIMAL | CPU cluster 0 temperature (°C) |
| `cpu_temp_1_c` | DECIMAL | CPU cluster 1 temperature (°C) |
| `random` | INTEGER | Random integer (connectivity heartbeat) |

## Commands

| Command | Parameter | Description |
|---------|-----------|-------------|
| `file-download` | URL | Download and apply an OTA update package |
