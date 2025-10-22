# NXP FRDM i.MX 93 Development Board QuickStart

>[!TIP]
> To set up and connect this device using the **AWS greengrass Lite SDK**, refer to this [QuickStart Guide](https://github.com/avnet-iotconnect/iotc-python-greengrass-demos/blob/main/nxp-frdm-imx-93/)

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Cloud Account Setup](#4-cloud-account-setup)
5. [Device Setup](#5-device-setup)
6. [Onboard Device](#6-onboard-device)
7. [Using the Demo](#7-using-the-demo)
8. [EIQ Vison AI Driver Monitoring System Demo](#8-eiq-vison-ai-driver-monitoring-system-demo)
9. [Troubleshooting](#9-troubleshooting)
10. [Resources](#10-resources)

# 1. Introduction

This guide provides step-by-step instructions to set up the NXP FRDM i.MX 93 hardware and integrate it with /IOTCONNECT,
Avnet's robust IoT platform.

<table>
  <tr>
    <td><img src="./media/FRDM93.png" width="6000"></td>
    <td>The FRDM i.MX 93 development board is a low-cost and compact development board featuring the i.MX93 applications processor. Equipped with an onboard IW612 module, featuring NXP's Tri-Radio solution with Wi-Fi 6 + Bluetooth 5.4 + 802.15.4, the board is ideal for developing modern Industrial and IoT applications.</td>
  </tr>
</table>

# 2. Requirements

## Hardware

* NXP FRDM i.MX 93 Development Board [Purchase](https://export.farnell.com/nxp/frdm-imx93/frdm-development-board-for-i-mx/dp/4626785) | [User Manual & Kit Contents](https://docs.nxp.com/bundle/UM12181/page/topics/frdm-imx93_overview.html) | [All Resources](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDM-IMX93)
* 2x USB Type-C Cables (included in kit)
* (Optional) Ethernet Cable
* (Optional) WiFi Network SSID and Password

## Software

* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases)
  or [PuTTY](https://www.putty.org/)

# 3. Hardware Setup

See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/FRDM93-connections.jpg" width="600">
</details>

Using the above image as reference, make the following connections:

1. Connect an Ethernet cable from your LAN (router/switch) to the Ethernet connector labeled **#1**. If you instead wish
   to use Wi-Fi, after booting your board refer to the [WIFI](WIFI.md) guide.
2. Connect one of the included USB cables from your PC to the USB-C connector labeled **#2**.
3. Connect the other included USB cable from your PC to the USB-C connector labeled **#3**.

# 4. Cloud Account Setup

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

# 5. Device Setup

1. Open a serial terminal emulator program such as TeraTerm.
2. Ensure that your serial settings in your terminal emulator are set to:

- Baud Rate: 115200
- Data Bits: 8
- Stop Bits: 1
- Parity: None

3. Starting with the lowest COM port value for "USB Serial Device" in the Device Manager list, attempt to connect to
   your board via the terminal emulator

> [!NOTE]
> A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key
> to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.

4. When prompted for a login, type `root` followed by the ENTER key.
5. Run these commands to update the core board packages and install necessary /IOTCONNECT packages:

```
sudo apt-get update
```

```
python3 -m pip install iotconnect-sdk-lite requests
```

6. Run this command to create and move into a directory for your demo files:

```
mkdir -p /home/weston/demo && cd /home/weston/demo
```

> [!TIP]
> To gain access to "copy" and "paste" functions inside of a Putty terminal window, you can CTRL+RIGHTCLICK within the
> window to utilize a dropdown menu with these commands. This is very helpful for copying/pasting between your browser and
> the terminal.

# 6. Onboard Device

The next step is to onboard your device into /IOTCONNECT. This will be done via the online /IOTCONNECT user interface.

Follow [this guide](../common/general-guides/UI-ONBOARD.md) to walk you through the process.

> [!TIP]
> If you have obtained a solution key for your /IOTCONNECT account from Softweb Solutions, you can utilize the /IOTCONNECT 
> REST API to automate the device onboarding process via shell scripts. Check out [this guide](../common/general-guides/REST-API-ONBOARD.md) 
> for more info on that.

# 7. Using the Demo

Run the basic demo with this command:

```
python3 app.py
```

> [!NOTE]
> Always make sure you are in the ```/home/weston/demo``` directory before running the demo. You can move to this
> directory with the command: ```cd /home/weston/demo```

View the random-integer telemetry data under the "Live Data" tab for your device on /IOTCONNECT.

# 8. EIQ Vison AI Driver Monitoring System Demo

After completing the basic demo setup, you will be able to perform an OTA update to automatically install and begin
running the EIQ Vision AI Driver Monitoring System Demo on your NXP i.MX 93. Refer
to [this guide](./dms-demo/README.md).

# 9. Troubleshooting

To return the board to an out-of-box state, refer to the [flashing](FLASHING.md) guide.

# 10. Resources
* Explore connecting the NXP FRDM i.MX 93 through the AWS Greengrass Lite SDK [QuickStart](https://github.com/avnet-iotconnect/iotc-python-greengrass-demos/blob/main/nxp-frdm-imx-93/)
* [Webinar Slides](Avnet-NXP-iMX93-EdgeAI-Webinar-Feb2025.pdf) | [Webinar QuickStart](dms-demo/WEBINAR_QUICKSTART.md)
* [Purchase the FRDM i.MX 93 Board](https://export.farnell.com/nxp/frdm-imx93/frdm-development-board-for-i-mx/dp/4626785)
* [More /IOTCONNECT NXP Guides](https://avnet-iotconnect.github.io/partners/nxp/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
