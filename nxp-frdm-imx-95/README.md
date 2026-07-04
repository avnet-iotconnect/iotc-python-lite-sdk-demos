# NXP FRDM i.MX 95 Development Board QuickStart

[Purchase NXP FRDM i.MX 95 Development Board](https://www.avnet.com/americas/product/nxp/frdm-imx95/evolve-122131125/)

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Device Setup](#4-device-setup)
5. [Onboard Device](#5-onboard-device)
6. [Using the Demo](#6-using-the-demo)
7. [eIQ GenAI Flow Edge LLM Demo](#7-eiq-genai-flow-edge-llm-demo)
8. [Troubleshooting](#8-troubleshooting)
9. [Going Further: Expansion Demos](#9-going-further-expansion-demos)
10. [Resources](#10-resources)

# 1. Introduction

This guide provides step-by-step instructions to set up the NXP FRDM i.MX 95 hardware and integrate it with /IOTCONNECT,
Avnet's robust IoT platform.

<!-- TODO: add a board photo to ./media/FRDM95.png and restore the two-column intro table used by the other boards -->

The FRDM i.MX 95 development board is a low-cost, compact development platform featuring the i.MX 95 applications
processor with 6x Arm Cortex-A55 cores, an Arm Cortex-M7 real-time core, an Arm Cortex-M33 safety core, and the
integrated **eIQ Neutron NPU (2 TOPS)** for on-device machine learning — including Generative AI / small language
models via NXP's eIQ GenAI Flow software pipeline. The board includes 8 GB LPDDR4X, 32 GB eMMC, a microSD slot, and an
onboard IW612 module featuring NXP's Tri-Radio solution with Wi-Fi 6 + Bluetooth 5.4 + 802.15.4, making it ideal for
modern industrial, IoT, and edge AI applications.

# 2. Requirements

## Hardware

* NXP FRDM i.MX 95 Development Board [Purchase](https://www.avnet.com/americas/product/nxp/frdm-imx95/evolve-122131125/) | [All Resources](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDM-IMX95)
* 2x USB Type-C Cables
* (Optional) Ethernet Cable
* (Optional) WiFi Network SSID and Password
* (Optional, for the GenAI voice pipeline) USB headset or USB speaker + microphone
* (Optional, for the ask-vlm vision demo) UVC-compliant USB webcam

## Software

* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases)
  or [PuTTY](https://www.putty.org/)

# 3. Hardware Setup

1. Connect an Ethernet cable from your LAN (router/switch) to the Ethernet connector. If you instead wish
   to use Wi-Fi, after booting your board refer to the [WIFI](WIFI.md) guide.
2. Connect a USB cable from your PC to the **DEBUG** USB-C port.
3. Connect a USB cable from your PC (or a USB-C power supply) to the **POWER** USB-C port.

> [!NOTE]
> The FRDM i.MX 95 ships from the factory with a pre-built NXP Linux demo image already flashed to the eMMC, so it will
> boot directly into Linux out of the box. The eIQ GenAI Flow demo requires a recent BSP (L6.12.49-2.2.0 or later
> recommended) — if your board has an older image, first re-flash it using the [flashing guide](FLASHING.md).

# 4. Device Setup

1. Open a serial terminal emulator program such as TeraTerm.
2. Ensure that your serial settings in your terminal emulator are set to:

- Baud Rate: 115200
- Data Bits: 8
- Stop Bits: 1
- Parity: None

3. The board's WCH USB-serial converter enumerates **four** serial ports on your PC. The Linux (Cortex-A55) console is
   the **first** port of the group (the second port is the System Manager debug monitor on the Cortex-M33). On a
   Windows host, connect to the lowest COM port value of the board's "USB Quad_Serial" devices in Device Manager; on a
   Linux host this is typically `/dev/ttyACM0`.

> [!NOTE]
> A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key
> to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.

4. When prompted for a login, type `root` followed by the ENTER key.
5. Run this command to install the necessary /IOTCONNECT packages:

```
python3 -m pip install iotconnect-sdk-lite requests
```

6. Run this command to create and move into a directory for your demo files:

```
mkdir -p /opt/demo && cd /opt/demo
```

> [!TIP]
> To gain access to "copy" and "paste" functions inside of a PuTTY terminal window, you can CTRL+RIGHTCLICK within the
> window to utilize a dropdown menu with these commands. This is very helpful for copying/pasting between your browser and
> the terminal.

# 5. Onboard Device

The next step is to onboard your device into /IOTCONNECT. This will be done via the online /IOTCONNECT user interface.

Follow [this guide](../common/general-guides/UI-ONBOARD.md) to walk you through the process.

> [!TIP]
> If you have obtained a solution key for your /IOTCONNECT account from Softweb Solutions, you can utilize the /IOTCONNECT
> REST API to automate the device onboarding process via shell scripts. Check out [this guide](../common/general-guides/REST-API-ONBOARD.md)
> for more info on that.

# 6. Using the Demo

Run the basic demo with this command:

```
python3 app.py
```

> [!NOTE]
> Always make sure you are in the ```/opt/demo``` directory before running the demo. You can move to this
> directory with the command: ```cd /opt/demo```

View the random-integer telemetry data under the "Live Data" tab for your device on /IOTCONNECT.

# 7. eIQ GenAI Flow Edge LLM Demo

After completing the basic demo setup, you can upgrade your device to run **on-device Generative AI**. The expansion
demo integrates NXP's [eIQ GenAI Flow](https://www.nxp.com/design/design-center/software/embedded-software/eiq-genai-flow-conversational-ai-software-pipeline-on-edge-devices:GEN-AI-FLOW)
conversational AI pipeline (LLM, speech-to-text, text-to-speech, RAG) with /IOTCONNECT, letting you prompt an LLM
running on the i.MX 95 from the cloud and stream live LLM performance metrics (tokens/sec, time-to-first-token, CPU
load, memory) to your /IOTCONNECT dashboard. Refer to [this guide](./genai-flow-demo/README.md).

> [!NOTE]
> The GenAI models run today on the i.MX 95's Cortex-A55 CPU cluster and (experimentally) on the integrated eIQ Neutron
> NPU. Support for the **Kinara Ara-2 discrete NPU module** — which dramatically accelerates larger LLMs — will be added
> to this demo once the module is available.

# 8. Troubleshooting

To return the board to an out-of-box state, or to update to the latest NXP demo image, refer to
the [flashing](FLASHING.md) guide.

# 9. Going Further: Expansion Demos

Now that you have completed the basic quickstart, you can install a specialized expansion demo on top of it using a
software package. The following expansion demos are available for this board:

* **[eIQ GenAI Flow Edge LLM Demo](genai-flow-demo/README.md)**: Upgrades the starter demo to an on-device Generative
  AI showcase powered by NXP's eIQ GenAI Flow pipeline. Prompt an on-device LLM from /IOTCONNECT, run the official
  GenAI Flow benchmark, and stream LLM performance telemetry to the cloud.

# 10. Resources

* [Purchase the FRDM i.MX 95 Board](https://www.avnet.com/americas/product/nxp/frdm-imx95/evolve-122131125/)
* [NXP FRDM-IMX95 Product Page](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDM-IMX95)
* [NXP i.MX 95 Applications Processor Family](https://www.nxp.com/products/i.MX95)
* [NXP eIQ GenAI Flow](https://www.nxp.com/design/design-center/software/embedded-software/eiq-genai-flow-conversational-ai-software-pipeline-on-edge-devices:GEN-AI-FLOW)
* [eIQ GenAI Flow Demonstrator (GitHub)](https://github.com/nxp-appcodehub/dm-eiq-genai-flow-demonstrator)
* [More /IOTCONNECT NXP Guides](https://avnet-iotconnect.github.io/partners/nxp/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
