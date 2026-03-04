# Microchip PolarFire SoC Discovery Kit QuickStart
 [Purchase Microchip PolarFire SoC Discovery Kit](https://www.newark.com/microchip/mpfs-disco-kit/discovery-kit-64bit-risc-v-polarfire/dp/97AK2474)
1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Software Setup](#4-software-setup)
5. [/IOTCONNECT: Cloud Account Setup](#5-iotconnect-cloud-account-setup)
6. [Device Setup](#6-device-setup)
7. [Onboard Device](#7-onboard-device)
8. [Using the Basic Demo](#8-using-the-basic-demo)
9. [Deploying Additional Demos](#9-deploying-additional-demos)
10. [Resources](#10-resources)

# 1. Introduction

This guide provides step-by-step instructions to set up the **Microchip PolarFire SoC Discovery Kit hardware** and integrate
it with **/IOTCONNECT**, Avnet's robust IoT platform. The PolarFire SoC Discovery Kit hardware platform provides flexible options
for IoT application development, enabling secure device onboarding, telemetry collection, and over-the-air (OTA) updates.

<table>
  <tr>
    <td><img src=".//media/polarfire-product.png" width="6000"></td>
    <td>This open-source development kit features a quad-core, 64-bit CPU cluster based on the RISC-V application-class 
processor that supports Linux® and real-time applications, a rich set of peripherals and 95K of low-power, high-performance 
FPGA logic elements. The kit is ready for rapid testing of applications in an easy-to-use hardware development platform and 
offers a mikroBUS™ expansion header for Click boards™, a 40-pin Raspberry Pi™ connector, and a MIPI® video connector. 
The expansion boards can be controlled using protocols like I2C and SPI. One GB of DDR4 memory is available as well as 
a microSD® card slot for booting Linux. Communication interfaces include one Gigabit Ethernet connector and three UART 
connections via the USB type C connector. An on-board FlashPro5 programmer is available to program and debug the PolarFire 
FPGA through USB-to-JTAG channel.</td>
  </tr>
</table>

# 2. Requirements

This guide has been written and tested to work on a Windows 10/11 PC. However, there is no reason this can't be
replicated in other environments.

## Hardware

* Microchip PolarFire SoC Discovery Kit [Purchase](https://www.newark.com/microchip/mpfs-disco-kit/discovery-kit-64bit-risc-v-polarfire/dp/97AK2474) | [User Manual & Kit Contents](https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/PolarFire_SoC_FPGA_Discovery_Kit_User_Guide.pdf) | [All Resources](https://www.microchip.com/en-us/development-tool/mpfs-disco-kit)
* Ethernet Cable
* USB-C Cable (included in kit)
* High Quality SanDisk UHS-1 Class 10 A1/A2 Micro-SD card

> [!IMPORTANT]
> The PolarFire SoC Discovery Kit requires a **High Quality, name brand UHS-1 Class 10 A1/A2 Micro-SD card**. Other brands or specs will 
> not work properly with this board.

## Software

* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases)
  or [PuTTY](https://www.putty.org/)
* An SD-Card flashing utility such as [Balena Etcher](https://etcher.balena.io/)
* Latest Microchip "Programming and Debug" package for your OS [from this page](https://www.microchip.com/en-us/products/fpgas-and-plds/fpga-and-soc-design-tools/programming-and-debug/lab). Click the "Software Download Archive" to find the download link. Do NOT download the Libero SoC Design Suite.


# 3. Hardware Setup

See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/board-connections.png" width="600">
</details>

Using the above image as reference, make the following connections:

1. Connect the included USB-C cable from your PC to the USB-C connector labeled **#1**.
2. Connect an Ethernet cable from your LAN (router/switch) to the Ethernet connector labeled **#2**.

# 4. Software Setup

## Update FPGA
1. Download the latest pre-built programming file (MPFS_DISCOVERY_KIT_XXXX_XX.zip) from [here](https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design/releases)
and then extract the package and locate the **.job** file. 
2. Ensure that the board is connected to your PC via the USB-C cable, as instructed in the Hardware Setup.
3. Open FlashPro Express, and click  **New Job Project**
4. For the "Import FlashPro Express job file", click **Browse...** and select the downloaded `MPFS_DISCOVERY_KIT_XXXX_XX.job` file just extracted.
5. For the "FlashPro Express job project location" click **Browse...** and create/choose a folder near the root of your drive (eg `C:\Microchip\PolarFire`) and click **OK**
6. After the new project has loaded, click the **RUN** button to flash the board.
7. After the flash has completed disconnect the USB cable from the board.

## Flash Linux Image
1. Download the latest Linux Image release for the PolarFire SoC Discovery Kit by navigating the [linux4microchip PolarFire
SoC Releases page](https://github.com/linux4microchip/meta-mchp/releases), scrolling down to the "Pre-built images for 
the Discovery Kit Reference Design" section and clicking on the "pre-built image" link. The downloaded filename should
be similar to `mchp-base-image-mpfs-disco-kit.rootfs-xxxxxxxxxxxxxx.wic.gz"
2. Extract the image so that you have a `.wic` file.
3. Use an SD-Card flashing utility, such as Balena Etcher, to flash the `.wic` file to the micro-SD card.
4. After flashing, insert the Micro-SD card into the Micro-SD card slot on the PolarFire SoC Discovery Kit.
5. Reconnect the USB cable to the board.

# 5. /IOTCONNECT: Cloud Account Setup

An /IOTCONNECT account with AWS backend is required. If you need to create an account, a free trial subscription is
available.
The free subscription may be obtained directly from iotconnect.io or through the AWS Marketplace.

* Option #1 (
  Recommended) [/IOTCONNECT via AWS Marketplace](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/iotconnect_aws_marketplace.md) -
  60 day trial; AWS account creation required
* Option #2 [/IOTCONNECT via iotconnect.io](https://subscription.iotconnect.io/subscribe?cloud=aws) - 30 day trial; no
  credit card required

> [!NOTE]
> Be sure to check any SPAM folder for the temporary password after registering.

# 6. Device Setup

1. Open a serial terminal emulator program such as TeraTerm.
2. Ensure that your serial settings in your terminal emulator are set to:

- Baud Rate: 115200
- Data Bits: 8
- Stop Bits: 1
- Parity: None

3. Click **File** -> **New connection...** -> **Serial** and observe 3 COM port entries for the PolarFire SoC Discovery Kit.
4. Select the **middle-numbered port.** For example, given these COM ports:

* COM10
* COM11
* COM12

You would connect to COM11.

> [!NOTE]
> A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key
> to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.

4. When prompted for a login, type `root` followed by the ENTER key.
5. Run these commands to update the core board packages and install necessary /IOTCONNECT packages:

```
sudo opkg update
```

```
python3 -m pip install iotconnect-sdk-lite requests
```

6. Then run these commands to create and move into a directory for your demo files:

```
mkdir -p /opt/demo && cd /opt/demo
```

# 7. Onboard Device

The next step is to onboard your device into /IOTCONNECT. This will be done via the online /IOTCONNECT user interface.

Follow [this guide](../common/general-guides/UI-ONBOARD.md) to walk you through the process.

# 8. Using the Basic Demo

Run the basic demo with this command:

```
python3 app.py
```

> [!NOTE]
> Always make sure you are in the ```/opt/demo``` directory before running the demo. You can move to this
> directory with the command: ```cd /opt/demo```

View the random-integer telemetry data under the "Live Data" tab for your device on /IOTCONNECT.

# 9. Deploying Additional Demos

Three demos are available that each utilize a different inference approach implemented in the FPGA fabric, progressing from a simple hand-crafted classifier up to a trained multi-layer neural network with batch processing.

- [Template Correlation Classifier](ml-template-correlation-classifier/):  
Classifies by dot-product correlation against three hand-crafted waveform templates. No neural network, no training required.
- [Simple Neural Network Accelerator](ml-simple-nn-accelerator/):  
Demo with a real neural network in FPGA fabric. One hidden layer with fixed integer weights, no training required.
- [Complex Neural Network Accelerator](ml-complex-nn-accelerator/):  
Two hidden layers with ~11K trained weights and batch-aware DMA execution. Hardware acceleration throughput is most visible

## Demo Block Diagrams:

<img src="./images/classification_methods.svg" alt="Expansion demo comparison diagram" width="900" />

# 10. Resources

* [Technical Deep Dive](tech-reference.md)
* [Purchase the Microchip PolarFire SoC Discovery Kit](https://www.newark.com/microchip/mpfs-disco-kit/discovery-kit-64bit-risc-v-polarfire/dp/97AK2474)
* [More /IOTCONNECT Microchip Guides](https://avnet-iotconnect.github.io/partners/microchip/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
