# NXP FRDM i.MX 93 Development Board QuickStart

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Cloud Account Setup](#4-cloud-account-setup)
5. [Device Setup](#5-device-setup)
6. [Using the Demo](#6-using-the-demo)
7. [Troubleshooting](#7-troubleshooting)
8. [Resources](#8-resources)


# 1. Introduction
This guide is designed to walk through the steps to connect the NXP FRDM i.MX 93 to the Avnet /IOTCONNECT platform and demonstrate a Driver Monitoring Solution (DMS) demo by leveraging local AI on the NPU.

<table>
  <tr>
    <td><img src="./media/FRDM93.png" width="6000"></td>
    <td>The FRDM i.MX 93 development board is a low-cost and compact development board featuring the i.MX93 applications processor. Equipped with an onboard IW612 module, featuring NXP's Tri-Radio solution with Wi-Fi 6 + Bluetooth 5.4 + 802.15.4, the board is ideal for developing modern Industrial and IoT applications.</td>
  </tr>
</table>

# 2. Requirements

## Hardware 
* NXP FRDM i.MX 93 Development Board [Purchase](https://www.avnet.com/shop/us/products/nxp/frdm-imx93-3074457345660216004/) | [User Manual & Kit Contents](https://docs.nxp.com/bundle/UM12181/page/topics/frdm-imx93_overview.html) | [All Resources](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDM-IMX93)
* 2x USB Type-C Cables (included in kit)
* (Optional) Ethernet Cable
* UVC-Compliant Webcam
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
1. Connect an Ethernet cable from your LAN (router/switch) to the Ethernet connector labeled **#1**. If you instead wish to use Wi-Fi, after booting your board refer to the [WIFI](WIFI.md) guide.
2. Connect a uvc-compliant webcam to the USB-A connector labeled **#4**.
3. Connect an HDMI cable from a monitor/display to the HDMI connector port labeled **#5**.
4. Lastly, connect the included USB cables from your PC to the USB-C connectors labeled **#2** and **#3** to power on the board.

# 4. Cloud Account Setup
An /IOTCONNECT account with AWS backend is required.  If you need to create an account, a free trial subscription is available.
The free subscription may be obtained directly from iotconnect.io or through the AWS Marketplace.


* Option #1 (Recommended) [/IOTCONNECT via AWS Marketplace](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/iotconnect_aws_marketplace.md) - 60 day trial; AWS account creation required
* Option #2 [/IOTCONNECT via iotconnect.io](https://subscription.iotconnect.io/subscribe?cloud=aws) - 30 day trial; no credit card required



> [!NOTE]
> Be sure to check any SPAM folder for the temporary password after registering.

# 5. Device Setup
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
5. Run these commands to update the core board packages and install necessary IoTConnect packages:
   ```
   sudo apt-get update
   python3 -m pip install iotconnect-sdk-lite
   python3 -m pip install iotconnect-rest-api
   ```
6. Run these commands to create and move into a directory for your demo files:
   ```
   mkdir /home/weston/demo
   cd /home/weston/demo
   ```
>[!TIP]
>To gain access to "copy" and "paste" functions inside of a Putty terminal window, you can CTRL+RIGHTCLICK within the window to utilize a dropdown menu with these commands. This is very helpful for copying/pasting between your borswer and the terminal.

7. Run this command to first protect your IoTConnect credentials:
   ```
   export HISTCONTROL=ignoreboth
   ```
   Then run this IoTConnect REST API CLI command (with your credentials substituted in) to log into your IoTConnect account on the device:
   ```
   iotconnect-cli configure -u my@email.com -p "MyPassword" --pf mypf --env myenv --skey=mysolutionkey
   ```
   For example if these were your credentials:
   * Email: `john.doe@gmail.com`
   * Password: Abc123!
   * Platform: aws
   * Environment: technology
   * Solution Key: AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
     
   Your login command would be:
   ```
   iotconnect-cli configure -u john.doe@gmail.com -p "Abc123!" --pf aws --env technology --skey=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
   ```
   You will see this output in the console if your login succeeded:
   ```
   Logged in successfully.
   ```

8. Run this command to download and run the device setup script:
   ```
   curl -sOJ 'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/files/setup-files/device-setup.py' && python3 device-setup.py
   ```

# 6. Using the Demo
1. Run the basic demo with this command:
```
python3 app.py
```
>[!NOTE]
>Always make sure you are in the ```/home/weston/demo``` directory before running the demo. You can move to this directory with the command: ```cd /home/weston/demo```

2. View the random-integer telemetry data under the "Live Data" tab for your device on /IOTCONNECT.

# 7. EIQ Vison AI Driver Monitoring System Demo
After completing the basic demo setup, you will be able to perfrom an OTA update to automatically install and begin running the EIQ Vision AI Driver Monitoring System Demo on your NXP i.MX 93. Refer to [this guide](./dms-demo/README.md).

# 8. Troubleshooting

To return the board to an out-of-box state, refer to the [flashing.md](flashing.md) guide.

# 9. Resources
* [Webinar Slides](Avnet-NXP-iMX93-EdgeAI-Webinar-Feb2025.pdf)
* [Purchase the FRDM i.MX 93 Board](https://www.avnet.com/shop/us/products/nxp/frdm-imx93-3074457345660216004/)
* [More /IOTCONNECT NXP Guides](https://avnet-iotconnect.github.io/partners/nxp/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
