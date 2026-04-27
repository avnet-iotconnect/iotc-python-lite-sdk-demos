# Renesas RZ/V2H EVK Quickstart
[Purchase the Renesas RZ/V2H EVK](https://www.renesas.com/en/design-resources/boards-kits/rz-v2h-evk)

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Device Setup](#4-device-setup)
5. [Onboard Device](#5-onboard-device)
6. [Using the Demo](#6-using-the-demo)
7. [Going Further: AI Demo](#7-going-further-ai-demo)
8. [Resources](#8-resources)

# 1. Introduction

This guide walks through connecting the Renesas RZ/V2H Evaluation Kit (EVK) to the Avnet /IOTCONNECT platform,
demonstrating telemetry collection, cloud-to-device commands, and AI inference reporting via the on-board DRP-AI
hardware accelerator.

The RZ/V2H EVK features Renesas' dedicated **DRP-AI** (Dynamically Reconfigurable Processor for AI) hardware
accelerator, which runs deep-learning inference workloads at low power. This demo wraps the pre-built AI
application binaries from the Renesas AI SDK, streams their results to /IOTCONNECT, and adds real-time
system performance monitoring alongside cloud-controllable AI demo management.

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

# 3. Hardware Setup

Follow the [Renesas RZ/V2H Getting Started Guide](https://renesas-rz.github.io/rzv_ai_sdk/latest/getting_started_v2h.html) to:

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

# 5. Onboard Device

Onboard your device into /IOTCONNECT by following the
[UI Onboarding Guide](../common/general-guides/UI-ONBOARD.md).

When prompted for a device template, import the template JSON from whichever demo you are running:

* **System Monitor Demo**: `system-monitor-demo/rzv2h-system-monitor-template.json`
* **AI Demo**: `ai-demo/rzv2h-ai-template.json`

Place the three credential files in `/opt/demo`:

* `iotcDeviceConfig.json`
* `device-cert.pem`
* `device-pkey.pem`

# 6. Using the Demo

Deploy and run the System Monitor Demo:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/renesas-rzv2h-evk/system-monitor-demo/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

Then run:

```bash
python3 app.py
```

> [!NOTE]
> Always make sure you are in the `/opt/demo` directory before running the demo. You can move to this directory with the command: `cd /opt/demo`

View the telemetry under the **Live Data** tab for your device in /IOTCONNECT.

# 7. Going Further: AI Demo

Head to the **[AI Demo Guide](ai-demo/README.md)** for the advanced AI inference demo.

This demo runs Python-based computer-vision inference on the USB camera, launches and controls any of the 14 Renesas AI SDK DRP-AI demos on the HDMI display via C2D commands, and streams detection counts, inference timing, and system performance metrics to /IOTCONNECT in real time.

# 8. Resources

* [Purchase the Renesas RZ/V2H EVK](https://www.renesas.com/en/design-resources/boards-kits/rz-v2h-evk)
* [Renesas RZ/V2H AI SDK](https://www.renesas.com/en/software-tool/rzv2h-ai-software-development-kit)
* [Renesas RZ/V2H Getting Started Guide](https://renesas-rz.github.io/rzv_ai_sdk/latest/getting_started_v2h.html)
* [Renesas AI Applications GitHub](https://github.com/renesas-rz/rzv_ai_sdk)
* [Renesas RZ GitHub](https://github.com/renesas-rz)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
