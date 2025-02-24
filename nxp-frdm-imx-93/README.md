# NXP FRDM i.MX 93 Development Board QuickStart

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [/IOTCONNECT: Cloud Account Setup](#4-iotconnect-cloud-account-setup)
5. [/IOTCONNECT: Device Template Setup](#5-iotconnect-device-template-setup)
6. [Run Setup Scripts](#6-run-setup-scripts)
7. [/IOTONNECT: Create Device](#7-iotconnect-create-device)
8. [Start the Application and Verify Data](#8-start-the-application-and-verify-data)
9. [/IOTCONNECT: Import Dashboard Template](#9-iotconnect-import-dashboard-template)
10. [/IOTCONNECT: Using the Dashboard](#10-iotconnect-using-the-dashboard)
11. [Troubleshooting](#11-troubleshooting)
12. [Resources](#12-resources)

# 1. Introduction
This guide is designed to walk through the steps to connect the NXP FRDM i.MX 93 to the Avnet /IOTCONNECT platform and demonstrate a Driver Monitoring Solution (DMS) by leveraging local AI on the NPU.

<table>
  <tr>
    <td><img src="./media/FRDM93.png" width="6000"></td>
    <td>The FRDM i.MX 93 development board is a low-cost and compact development board featuring the i.MX93 applications processor. Equipped with an onboard IW612 module, featuring NXP's Tri-Radio solution with Wi-Fi 6 + Bluetooth 5.4 + 802.15.4, the board is ideal for developing modern Industrial and IoT applications.</td>
  </tr>
</table>

# 2. Requirements
This guide has been written and tested to work on a Windows 10/11 PC. However, there is no reason this can't be replicated in other environments.

## Hardware 
* NXP FRDM i.MX 93 Development Board [Purchase](https://www.avnet.com/shop/us/products/nxp/frdm-imx93-3074457345660216004/) | [User Manual & Kit Contents](https://docs.nxp.com/bundle/UM12181/page/topics/frdm-imx93_overview.html) | [All Resources](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDM-IMX93)
* 2x USB Type-C Cables (included in kit)
* Ethernet Cable
* Webcam
* HDMI Cable
* 2nd Monitor
* (Optional) WiFi Network SSID and Password

## Software
* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases) or [PuTTY](https://www.putty.org/)

# 3. Hardware Setup
See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/board_setup.png" width="600">
</details>

Using the above image as reference, make the following connections:
1. Connect an Ethernet cable from your LAN (router/switch) to the Ethernet connector labeled **#1**.
2. Connect a webcam to the USB-A connector labeled **#4**.
3. Connect an HDMI cable from a monitor/display to the HDMI connector port labeled **#5**.
4. Lastly, connect the included USB cables from your PC to the USB-C connectors labeled **#2** and **#3** to power on the board.

# 4. /IOTCONNECT: Cloud Account Setup
An /IOTCONNECT account with AWS backend is required.  If you need to create an account, a free trial subscription is available.
The free subscription may be obtained directly from iotconnect.io or through the AWS Marketplace.


* Option #1 (Recommended) [/IOTCONNECT via AWS Marketplace](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/iotconnect_aws_marketplace.md) - 60 day trial; AWS account creation required
* Option #2 [/IOTCONNECT via iotconnect.io](https://subscription.iotconnect.io/subscribe?cloud=aws) - 30 day trial; no credit card required



> [!NOTE]
> Be sure to check any SPAM folder for the temporary password after registering.

# 5. /IOTCONNECT: Device Template Setup
A Device Template defines the type of telemetry the platform should expect to receive.
* Download the pre-made [Device Template](dms-demo/templates/eiqIOTC_template.JSON?raw=1) (**MUST** Right-Click and "Save-As" to get the raw json file)
* Import the template into your /IOTCONNECT instance. (A guide on [Importing a Device Template](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/import_device_template.md) is available.)

# 6. Run Setup Scripts
1. Open a serial terminal emulator program such as TeraTerm.
2. Ensure that your serial settings in your terminal emulator are set to:
  - Baud Rate: 115200
  - Data Bits: 8
  - Stop Bits: 1
  - Parity: None
3. Starting with the lowest COM port value for "USB Serial Device" in the Device Manager list, attempt to connect to your board via the terminal emulator
>[!NOTE]
>A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.
4. When prompted for a login, type `root` followed by the ENTER key.
5. Run the install script which will automate the installation of the i.MX eIQ Demo by perform the following actions:
   * Install Dependencies
   * Install /IOTCONNECT Python Lite SDK
   * Download AI-ML models
   * Start the interactive /IOTCONNECT onboarding script

   ```
   cd /home/weston
   curl -sOJ 'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/dms-demo/scripts/install.sh' && bash ./install.sh
   ```

# 7. /IOTCONNECT: Create Device
The script started in the previous step will guide you through the following steps:

1. Click the `Device` icon then the "Device" sub-menu
2. At the top-right, click on the `Create Device` button
3. Enter `FRDMiMX93` for both **Unique ID** and **Device Name**
4. Select the entity in the drop-down (if this is a new/trial account, there is only one option)
5. Select the template `eiqIOTC` from the template dropdown box
6. Change the Device Certificate as "Use my certificate"
7. Copy the Device Certificate displayed in the serial terminal and paste it into the box under "Certificate Text"

>[!CAUTION]
> Use the `Edit` -> `Copy` option as the Ctrl + C shortcut will interrupt the script.

8. Click `Save & View`
9. Click the "Paper and Cog" icon at top-right to download your device configuration file and save it to your working directory.
10. Open the downloaded file in a text editor and paste the content into the serial terminal and press `enter`
11. When prompted, press `y` and `enter` to download the eIQ AI Models

>[!NOTE]
>This process will take just over 8 minutes.

# 8. Start the Application and Verify Data
From the `/home/weston` directory, use the following command to the demo application:
```
python3 /home/weston/imx93-ai-demo.py
```

The telemetry data can be viewed and verified under the "Live Data" tab for your device on /IOTCONNECT.

>[!IMPORTANT]
>There needs to be a video capture device connected to the USB-A port on the board for the video to be processed.

# 9. /IOTCONNECT: Import Dashboard Template

* Download the demo [Dashboard Template](dms-demo/templates/NXP-IMX9eIQ_dashboard_export.json?raw=1) (**must** Right-Click, Save As)
* **Download** the template then select `Create Dashboard` from the top of the page
* **Select** the `Import Dashboard` option and click `browse` to select the template you just downloaded.
* **Select** `eiqIOTC` for **template** and `FRDMiMX93` for **device** 
* **Enter** a name (such as `FRDM i.MX 93 DSM Demo`) and click `Save` to complete the import

# 10. /IOTCONNECT: Using the Dashboard



# 11. Troubleshooting

To return the board to an out-of-box state, refer to the [flashing.md](flashing.md)

# 12. Resources
* [Purchase the FRDM i.MX 93 Board](https://www.avnet.com/shop/us/products/nxp/frdm-imx93-3074457345660216004/)
* [Other /IOTCONNECT NXP Guides](https://avnet-iotconnect.github.io/partners/nxp/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
