# NXP FRDM i.MX 93 Development Board QuickStart

1. [Introduction](#1-introduction)
2. [Hardware Requirements](#2-hardware-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Cloud Account Setup](#4-cloud-account-setup)
5. [/IOTCONNECT Device Template Setup](#5-iotconnect-device-template-setup)
6. [Device Setup](#6-device-setup)
7. [Using the Demo](#7-using-the-demo)
8. [Resources](#8-resources)

# 1. Introduction
This guide is designed to walk through the steps to connect the NXP FRDM i.MX 93 to the Avnet /IOTCONNECT platform and demonstrate a Driver Monitoring Solution (DMS) by leveraging local AI on the NPU.

<table>
  <tr>
    <td><img src="./media/FRDM93.png" width="6000"></td>
    <td>The FRDM i.MX 93 development board is a low-cost and compact development board featuring the i.MX93 applications processor. Equipped with an onboard IW612 module, featuring NXP's Tri-Radio solution with Wi-Fi 6 + Bluetooth 5.4 + 802.15.4, the board is ideal for developing modern Industrial and IoT applications.</td>
  </tr>
</table>

# 2. Hardware Requirements
* NXP FRDM i.MX 93 Development Board [Purchase](https://www.avnet.com/shop/us/products/nxp/frdm-imx93-3074457345660216004/) | [User Manual & Kit Contents](https://docs.nxp.com/bundle/UM12181/page/topics/frdm-imx93_overview.html) | [All Resources](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDM-IMX93)
* 2x USB Type-C Cables (included in kit)
* (Optional) 1x Ethernet Cable (and a local router/switch with Internet connectivity)
* (Optional) WiFi Network SSID and Password (more configuration is required for this method)

# 3. Hardware Setup
See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/FRDM93-connections.jpg">
</details>

1. (Optional) Connect an Ethernet cable from your LAN (router/switch) to the port labeled **#1** in the reference image.
2. Connect a USB-C cable from a 5V power souce (such as your host machine) to the port labeled **#2** in the reference image.
3. Connect a USB-C cable from your host machine to the port labeled **#3** in the reference image.

# 4. Cloud Account Setup
An /IOTCONNECT account with AWS backend is required.  If you need to create an account, a free trial subscription is available.

[/IOTCONNECT Free Trial (AWS Version)](https://subscription.iotconnect.io/subscribe?cloud=aws)

> [!NOTE]
> Be sure to check any SPAM folder for the temporary password after registering.

See the /IOTCONNECT [Subscription Information](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/subscription.md) for more details on the trial.

# 5. /IOTCONNECT Device Template Setup
A Device Template define the type of telemetry the platform should expect to receive.
* Download the pre-made [Device Template](https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk/refs/heads/main/files/plitedemo-template.json) (**MUST** Right-Click and "Save-As" to get the raw json file)
* Import the template into your /IOTCONNECT instance. (A guide on [Importing a Device Template](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/import_device_template.md) is available or for more information, please see the [/IOTCONNECT Documentation](https://docs.iotconnect.io/iotconnect/) website.)

# 6. Device Setup
1. With the board powered on and connected to your host machine, open your Device Manager and note the COM ports that are in use by a "USB Serial Device" (may be multiple).
2. Open a terminal emulator program such as TeraTerm or PuTTY on your host machine.
3. Ensure that your serial settings in your terminal emulator are set to:
  - Baud Rate: 115200
  - Data Bits: 8
  - Stop Bits: 1
  - Parity: None
4. Starting with the lowest COM port value for "USB Serial Device" in the Device Manager list, attempt to connect to your board via the terminal emulator
>[!NOTE]
>A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.
5. When prompted for a login, type `root` followed by the ENTER key.
6. Wifi Setup (**OPTIONAL**): To set up your board to use a wifi internet connection instead of an ethernet connection, you can follow the [simple guide in this same directory](WIFI.md).
7. Run the install script: This script automates installation of the i.MX eIQ Demo on the FRDM imx93 Board. It will install all of the dependencies, the IOTCONNECT Python Lite SDK, download the AI-ML models, and guide the user through onboarding their device into IOTCONNECT:
   ```
   cd /home/weston
   curl -sOJ 'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/dms-demo/scripts/install.sh' && bash ./install.sh
   ```
>[!IMPORTANT]
>The device template upload step of the quickstart script can be skipped since it was already taken care of in Step 5.

>[!NOTE]
>This script primarily covers device and certificate creation in /IOTCONNECT. It will require some copy/paste between your browser and the terminal window.

# 7. Using the Demo
1. Move into the correct directory and run the basic demo with these commands (can be copy and pasted as one):
```
cd /home/weston
python3 /home/weston/imx93-ai-demo.py
```
2. View the dummy telemetry data under the "Live Data" tab for your device on /IOTCONNECT.

# 8. Resources
* [Purchase the FRDM i.MX 93 Board](https://www.avnet.com/shop/us/products/nxp/frdm-imx93-3074457345660216004/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
