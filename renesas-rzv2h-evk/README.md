# Renesas RZ/V2H EVK Quickstart

[Renesas RZ/V2H EVK Product Page](https://www.renesas.com/en/design-resources/boards-kits/rz-v2h-evk)

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Device Setup](#4-device-setup)
5. [Onboard Device](#5-onboard-device)
6. [Using the Demo](#6-using-the-demo)
7. [AI Inference Demo](#7-ai-inference-demo)
8. [Resources](#8-resources)

---

# 1. Introduction

This guide walks through connecting the Renesas RZ/V2H Evaluation Kit (EVK) to the Avnet /IOTCONNECT platform,
demonstrating telemetry collection, cloud-to-device commands, and AI inference reporting via the on-board DRP-AI
hardware accelerator.

The RZ/V2H EVK features Renesas' dedicated **DRP-AI** (Dynamically Reconfigurable Processor for AI) hardware
accelerator, which runs deep-learning inference workloads at low power. This demo wraps the pre-built AI
application binaries from the Renesas AI SDK, streams their results to /IOTCONNECT, and adds real-time
system performance monitoring alongside cloud-controllable AI demo management.

---

# 2. Requirements

## Hardware

* Renesas RZ/V2H EVK (CPU Board + EXP Board)
* 100W USB PD power adapter
* USB Camera supporting YUYV 640×480 @ 30fps (e.g. Logitech BRIO, C920)
* 16GB+ microSD card (Transcend UHS-I microSD 300S recommended)
* HDMI monitor and cable
* Ethernet cable
* Micro USB cable (for serial debug console via CN12)
* (Optional) USB hub, USB keyboard and mouse for on-board terminal

## Software

* Linux host PC for flashing the microSD card (Ubuntu 22.04 recommended)
* Serial terminal application: [TeraTerm](https://github.com/TeraTermProject/teraterm/releases) or [PuTTY](https://www.putty.org/)
* Renesas RZ/V2H AI SDK — [download here](https://www.renesas.com/en/software-tool/rzv2h-ai-software-development-kit)
* An [/IOTCONNECT account](https://www.iotconnect.io/)

---

# 3. Hardware Setup

Follow the [Complete Setup Guide](../RZV2H_EVK_Setup_Guide.md) (sections 1–5) to:

1. Flash the RZ/V2H Yocto SD card image using `bmaptool`
2. Set DSW1 DIP switches for eSD boot (DSW1[4]=ON, DSW1[5]=OFF)
3. Connect USB camera, HDMI monitor, and Ethernet
4. Open serial console on CN12 at **115200 baud, 8N1**
5. Power on the board (SW3 to ON)

Connect the board to your network via Ethernet and note its IP address:

```
ip addr show
```

Verify your USB camera is detected:

```
v4l2-ctl --list-devices
```

You should see your USB camera listed under `/dev/video0`.

---

# 4. Device Setup

Log in as `root` via SSH or serial console, then run these one-time setup commands:

```bash
dnf update -y
```

```bash
python3 -m pip install iotconnect-sdk-lite requests
```

```bash
mkdir -p /opt/demo && cd /opt/demo
```

> [!NOTE]
> The RZ/V2H runs Yocto Linux. Use `dnf` (not `apt`) for system packages.
> Python packages install system-wide as root — no virtualenv is needed.

---

# 5. Onboard Device

Onboard your device into /IOTCONNECT by following the
[UI Onboarding Guide](../common/general-guides/UI-ONBOARD.md).

When prompted for a device template, import the template JSON from whichever demo you are running:

* **Starter Demo**: `starter-demo/rzv2h-starter-template.json`
* **AI Demo**: `ai-demo/rzv2h-ai-template.json`

Place the three credential files in `/opt/demo`:

* `iotcDeviceConfig.json`
* `device-cert.pem`
* `device-pkey.pem`

---

# 6. Using the Demo

Navigate to `/opt/demo` and run the starter demo:

```bash
cd /opt/demo
python3 app.py
```

This sends the following telemetry to /IOTCONNECT every 10 seconds:

| Attribute | Description |
|-----------|-------------|
| `sdk_version` | IoTConnect SDK version |
| `cpu_percent` | Overall CPU utilisation (%) |
| `memory_percent` | RAM usage (%) |
| `cpu_temp_0_c` | CPU core cluster 0 temperature (°C) |
| `cpu_temp_1_c` | CPU core cluster 1 temperature (°C) |
| `random` | Random integer (connectivity check) |

View the telemetry under the **Live Data** tab for your device in /IOTCONNECT.

---

# 7. AI Inference Demo

Head over to the **[AI Demo Guide](ai-demo/README.md)** to enable the cloud-controlled AI inference demo.

This advanced demo:
- Runs Python-based computer-vision inference on the USB camera
- Launches and controls the Renesas **DRP-AI** object-counter demos on the HDMI display via C2D commands
- Reports detection counts, inference timing, and system performance metrics to /IOTCONNECT

### Supported DRP-AI Demos (HDMI display output)

All 14 demos from the Renesas RZ/V2H AI SDK are supported. See the
[AI demo README](ai-demo/README.md) for the full matrix and telemetry mapping.
Highlights:

| Param | Demo | Category |
|-------|------|----------|
| `coco` / `animal` / `vehicle` | Q08 Object Counter | Detection (80 / animals / vehicles) |
| `meter` | Q13 Analog Meter Reader | Dual-model meter reading |
| `footfall` | Q01 Footfall Counter | People tracking |
| `face_auth` | Q02 Face Authentication | Face recognition |
| `parking` | Q03 Smart Parking | Parking slot monitoring |
| `fish_class` | Q04 Fish Classification | Species classification |
| `activity` | Q05 Suspicious Activity | Violence detection |
| `expiry` | Q06 Expiry Date Detection | OCR |
| `plant` | Q07 Plant Disease | Leaf classification |
| `crack` | Q09 Crack Segmentation | Infrastructure monitoring |
| `suspicious` | Q10 Suspicious Person | Detection |
| `fish_det` | Q11 Fish Detection | Detection |
| `yoga` | Q12 Yoga Pose | Keypoint + pose classifier |
| `r01` | R01 Object Detection | Generic COCO detection |

### C2D Commands

| Command | Parameter | Description |
|---------|-----------|-------------|
| `start_detection` | — | Start Python CV inference on USB camera |
| `stop_detection` | — | Stop Python CV inference |
| `launch_drpai` | see matrix above (14 options) | Launch any DRP-AI demo on HDMI display |
| `stop_drpai` | — | Stop DRP-AI demo |
| `set_confidence` | `0.0`–`1.0` | Adjust detection confidence threshold |
| `file-download` | URL | OTA update — download and apply a new package |

---

# 8. Resources

| Resource | Link |
|----------|------|
| RZ/V2H AI SDK | https://www.renesas.com/en/software-tool/rzv2h-ai-software-development-kit |
| RZ/V2H Getting Started | https://renesas-rz.github.io/rzv_ai_sdk/latest/getting_started_v2h.html |
| AI Applications GitHub | https://github.com/renesas-rz/rzv_ai_sdk |
| /IOTCONNECT Overview | https://www.iotconnect.io/ |
| /IOTCONNECT Knowledgebase | https://help.iotconnect.io/ |
| Renesas RZ GitHub | https://github.com/renesas-rz |
