# PolarFire SoC Discovery Kit Fabric Accel Demo (Build + Run Guide)

This document captures the full, reproducible steps to create and run the FIC0-only fabric acceleration demo used in the workshop.

## What this demo does

- Writes a known incrementing pattern into MSS LSRAM via UIO (preferred) or devmem2 (fallback).
- Reads the pattern back, validates it, and computes a checksum.
- Publishes telemetry to /IOTCONNECT with pass/fail, timing, and host health metrics.

## Prerequisites

- PolarFire SoC Discovery Kit
- USB-C cable (power + UART)
- Ethernet (DHCP)
- microSD card with a supported Linux image
- FlashPro Express installed on host
- IOTCONNECT account + device credentials

## FPGA programming file (.job)

Use the prebuilt AXI4 stream demo .job in this repo:

`microchip-polarfire-soc-dk/fpga-assets/AXI4_STREAM_DEMO_2025_07/MPFS_DISCOVERY_KIT_AXI4_STREAM_DEMO_2025_07/MPFS_DISCOVERY_KIT_AXI4_STREAM_DEMO_2025_07.job`

Program it with FlashPro Express:

1) Open FlashPro Express.
2) New Project, select the .job file above.
3) Click **RUN** to program the FPGA.
4) Power-cycle the board after programming.

## Board setup (quick)

- Power: USB-C
- UART: use the middle-numbered COM port for Linux console
- Ethernet: connect to DHCP network
- SD: insert the Linux image card

## Linux image

Use the standard Discovery Kit Linux image per the QuickStart for your release.

This demo prefers UIO:
- `/dev/uio0` should map MSS LSRAM at 0x6000_0000
- `/dev/uio1` should map DMA registers at 0x6001_0000

If your image does not provide UIO nodes, the demo will fall back to `devmem2`.

## Copy the demo to the board

On the host:

```
ssh root@BOARD_IP "mkdir -p /home/weston/demo/fabric-accel"
scp -r microchip-polarfire-soc-dk/workshops/archive/fabric-accel-demo/. root@BOARD_IP:/home/weston/demo/fabric-accel/
```

## Python dependencies

On the board:

```
sudo opkg update
python3 -m pip install iotconnect-sdk-lite requests
```

## IOTCONNECT onboarding files

Place these files in `/home/weston/demo/fabric-accel`:

- `iotcDeviceConfig.json`
- `device-cert.pem`
- `device-pkey.pem`

## Run the demo

One-shot sanity check:

```
cd /home/weston/demo/fabric-accel
sudo python3 app.py --once
```

Expected output:
- `Capture OK: True`
- `First: 1 Last: 256`

Continuous loop (telemetry every 10 seconds):

```
sudo python3 app.py
```

## IOTCONNECT commands

Define these device commands:

- `set-pattern <count>`
- `fpga-capture <count>`
- `set-led <mask>` or `set_leds <mask>` (optional)

Examples:

- `set-pattern 256`
- `fpga-capture 100`
- `set-led 0x1`

## UIO limits (important)

If `/dev/uio0` exposes only 0x1000 bytes, the usable payload is 0xE00 bytes after the 0x200 offset:

- Max samples = 0xE00 / 8 = 448

If you send `set-pattern 1024`, the app will reject it with:

`pattern_count too large for UIO map (max 448)`

Options:
- Use `set-pattern 448` or lower.
- Force devmem2: `FORCE_DEVMEM2=1 sudo python3 app.py`

## Telemetry fields (main)

- `fpga_pattern_count`
- `fpga_first`, `fpga_last`
- `fpga_last_expected`, `fpga_last_ok`
- `fpga_checksum`
- `fpga_ok`
- `fpga_ms`
- `cpu_mhz`, `load_1m`, `load_5m`, `load_15m`
- `mem_total_kb`, `mem_free_kb`, `mem_available_kb`
- `uptime_s`
- `disk_root_used_pct`
- `cpu_temp_c` (if available)

## Troubleshooting

- `fpga_ok=0` with error about pattern_count too large:
  - Use a smaller count or `FORCE_DEVMEM2=1`.
- `devmem2` errors:
  - Ensure you are root.
  - Verify `devmem2` is installed: `which devmem2`.
- `set-led` fails:
  - CoreGPIO may not be exposed in your DT/image; LED control is optional.

## Files used

- `fabric-accel-demo/app.py`
- `fabric-accel-demo/README.md`
- `microchip-polarfire-soc-dk/FPGA-ACCEL-WORKSHOP.md`
- `microchip-polarfire-soc-dk/fpga-assets/AXI4_STREAM_DEMO_2025_07/.../MPFS_DISCOVERY_KIT_AXI4_STREAM_DEMO_2025_07.job`
