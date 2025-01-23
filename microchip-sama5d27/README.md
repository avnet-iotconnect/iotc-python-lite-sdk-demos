# SAMA5D27 IoTConnect Integration Quickstart Guide

This guide provides step-by-step instructions to set up the **Microchip SAMA5D27 hardware** and integrate it with **IoTConnect**, Avnet's robust IoT platform. The SAMA5D27 hardware platform provides flexible options for IoT application development, enabling secure device onboarding, telemetry collection, and over-the-air (OTA) updates.

---

## Table of Contents
1. [Overview](#overview)
2. [Hardware Description](#hardware-description)
   - [Datasheet](#datasheet)
   - [Standard Kit Contents](#standard-kit-contents)
   - [User-Provided Items](#user-provided-items)
   - [3rd-Party Accessories](#3rd-party-accessories)
3. [Set Up Your Development Environment](#set-up-your-development-environment)
   - [Supported Operating Systems](#supported-operating-systems)
   - [Tools Installation](#tools-installation)
4. [Set Up Device Hardware](#set-up-device-hardware)
5. [Integration with IoTConnect](#integration-with-iotconnect)
6. [Additional Documentation](#additional-documentation)
7. [Troubleshooting](#troubleshooting)
8. [Revision Info](#revision-info)

---

## Overview

The SAMA5D27 hardware platform is based on the **Microchip SAMA5D27 System on Module (SOM)**, providing robust performance for IoT applications. Paired with **IoTConnect**, this platform enables secure connectivity, real-time data collection, and device management for various use cases, including industrial automation, healthcare, and smart home solutions.

---

## Hardware Description

### Datasheet
For detailed technical specifications of the SAMA5D27 hardware, refer to the official [Microchip SAMA5D27 SOM1 Evaluation Kit Datasheet](https://www.microchip.com/en-us/development-tool/atsama5d27-som1-ek1).

### Standard Kit Contents
The standard SAMA5D27 Evaluation Kit includes:
1. **SAMA5D27 Evaluation Board**.
2. **Power Adapter** (5V DC).
3. **Micro-USB Cable** for debugging and communication.
4. **Quick Start Guide** with initial setup instructions.

<img src=".//media/sama5d27-product.png" alt="SAMA5D27 Evaluation Kit"/>

*Note: The contents may vary depending on the distributor. Verify with your vendor.*

### User-Provided Items
To use the SAMA5D27 hardware, you will need:
1. **Host Computer**: For configuration and development.
2. **Ethernet Cable**: For network connectivity.
3. **MicroSD Card**: Required for booting or storing application data.

### 3rd-Party Accessories
Optional accessories to enhance the functionality of the SAMA5D27 platform include:
1. **USB-to-UART Adapters**: For debugging (e.g., FTDI cables).
2. **Expansion Boards**: Add-on boards to extend I/O or peripheral connectivity.

---

## Set Up Your Development Environment

### Supported Operating Systems
The SAMA5D27 platform supports the following operating systems:
1. **Host OS**:
   - Windows 10/11
   - Ubuntu 20.04 or later
   - macOS 11.0 or later
2. **Device OS**:
   - Yocto-based Linux distribution for the SAMA5D27 (Linux4SAM).

### Tools Installation
To develop and debug applications for the SAMA5D27, the following tools are required:
1. **Yocto Build Tools**:
   - Follow the instructions for setting up the Yocto build environment on the [Linux4SAM Documentation](https://www.linux4sam.org/bin/view/Linux4SAM/Sama5d27Som1EKMainPage#eMMC_support_on_SDMMC0).
2. **SDKs**:
   - Install the IoTConnect SDK available from the [IoTConnect Python Lite SDK](https://github.com/avnet-iotconnect/iotc-python-lite-sdk).
3. **Optional IDEs**:
   - VS Code or other text editors for development.

---

## Set Up Device Hardware

### Step 1: Flash Yocto Image to SD Card
1. [Click here](https://www.linux4sam.org/bin/view/Linux4SAM/Sama5d27Som1EKMainPage#eMMC_support_on_SDMMC0) to download the image for the SAMA5D27.
2. Download the image:

    <img src=".//media/image-download.png" alt="Yocto Image Download"/>

3. Follow the "Create a SD card with the demo" section of the instructions to flash the image to an SD card.

    > **Important**: Must use a full-size SD card or a micro-SD card with a full-size adapter.

---

### Step 2: Connect to the SAMA5D27 over Serial

1. Connect the Ethernet cable to the onboard Ethernet port for internet access.
2. Use the provided micro-USB cable to connect the SAMA5D27 to your computer via the **J10** micro-USB port:

    <img src="media/j10-diagram.png" alt="J10 Port Diagram"/>

    > **Note**: The USB connection also powers the board.

3. Check the COM port of the board in the Device Manager:

    <img src="media/device-manager.png" alt="Device Manager"/>

4. Connect to the board using a terminal emulator (e.g., PuTTY) with the following settings:

    <img src="media/putty.png" alt="PuTTY Settings"/>

5. Insert the SD card into the SD card slot.
6. Press the **NRST** button to reboot the board and boot from the SD card:

    <img src="media/reset-diagram.png" alt="Reset Button Diagram"/>

---

### Step 3: Set Up and Run the Python Lite SDK Demo

Follow the instructions in the [Python Lite SDK Quickstart Guide](https://github.com/avnet-iotconnect/iotc-python-lite-sdk/blob/main/QUICKSTART.md) to complete the demo setup and execution.

---

## Integration with IoTConnect

The SAMA5D27 Evaluation Kit supports seamless integration with **IoTConnect**. Using the IoTConnect SDK, you can:
- Provision devices for secure communication with AWS IoT Core.
- Send and receive telemetry data in real-time.
- Manage device firmware with over-the-air (OTA) updates.

Refer to the [IoTConnect SDK Documentation](https://github.com/avnet-iotconnect/iotc-python-lite-sdk) for more details.

---

## Additional Documentation

For further resources, visit:
- [SAMA5D27 Evaluation Kit Datasheet](https://www.microchip.com/en-us/development-tool/atsama5d27-som1-ek1)
- [Linux4SAM Documentation](https://www.linux4sam.org/bin/view/Linux4SAM/Sama5d27Som1EKMainPage#eMMC_support_on_SDMMC0)
- [IoTConnect SDK Documentation](https://github.com/avnet-iotconnect/iotc-python-lite-sdk)

---

## Troubleshooting

### Common Issues
1. **No Power**:
   - Ensure the power adapter is properly connected.
   - Verify the power LED is lit on the evaluation kit.
2. **No Debug Output**:
   - Check the USB-to-UART connection.
   - Confirm the terminal baud rate is set to 115200.
3. **IoTConnect Connection Issues**:
   - Verify the Ethernet cable is connected and the device has a valid IP address.
   - Ensure the correct credentials are loaded onto the device.

For additional assistance, refer to the [IoTConnect Troubleshooting Guide](https://github.com/avnet-iotconnect/iotc-python-lite-sdk/issues).

---

## Revision Info
![GitHub last commit](https://img.shields.io/github/last-commit/avnet-iotconnect/iotc-python-lite-sdk-demos?label=Last%20Commit)
- View the complete [Commit History](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/commits/main) for this repository.
- View changes to this document: [README.md History](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/commits/main/microchip-sama5d27/README.md).
