# TRIA Maaxboard OSM93 QuickStart

1. [Introduction](#1-introduction)
2. [Hardware Requirements](#2-hardware-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Cloud Account Setup](#4-cloud-account-setup)
5. [/IOTCONNECT Device Template Setup](#5-iotconnect-device-template-setup)
6. [Device Setup](#6-device-setup)
7. [Using the Demo](#7-using-the-demo)
8. [Resources](#8-resources)

# 1. Introduction
This guide is designed to walk through the steps to connect the TRIA Maaxboard OSM93 to the Avnet /IOTCONNECT platform and demonstrate the standard IoT function of telemetry collection.

<table>
  <tr>
    <td><img src="./media/OSM93-top-down.png" width="6000"></td>
    <td>The MaaXBoard OSM93 features an energy-efficient, combination CPU/MPU/NPU, high-performance OSM compute system based on the NXP i.MX93 processor. The i.MX 93 device is architected with 3 separate processing domains: An application domain that includes two Arm® Cortex®-A55 (2.7 GHz) cores,
a real time domain includes an Arm® Cortex®-M33 (250 MHz) core, and an on-board AI accelerator, Arm® Ethos-U65 MicroNPU for machine learning and computer vision applications.</td>
  </tr>
</table>

# 2. Hardware Requirements
* TRIA Maaxboard OSM93 [Purchase](https://www.avnet.com/wps/portal/us/products/avnet-boards/avnet-board-families/maaxboard/maaxboard-osm93/?srsltid=AfmBOooL0Urtjf-giP8lPzs6dEfdVctJvArptaDqgqr9XMGEeMTIqkF_) | [User Manual](https://www.avnet.com/wps/wcm/connect/onesite/80927648-7b98-4063-b91e-a8cb2e51e8a6/MaaXBoard+OSM93+User+Guide+v1.0.pdf?MOD=AJPERES&CACHEID=ROOTWORKSPACE.Z18_NA5A1I41L0ICD0ABNDMDDG0000-80927648-7b98-4063-b91e-a8cb2e51e8a6-pf2HBHv) | [All Resources](https://www.avnet.com/wps/portal/us/products/avnet-boards/avnet-board-families/maaxboard/maaxboard-osm93/?srsltid=AfmBOooL0Urtjf-giP8lPzs6dEfdVctJvArptaDqgqr9XMGEeMTIqkF_)
* 1x USB Type-C Cables (included in kit)
* 1x USB to TTL Serial 3.3V Adapter Cable (must be purchased separately, this is [the cable used by Avnet's engineer](https://www.amazon.com/Serial-Adapter-Signal-Prolific-Windows/dp/B07R8BQYW1/ref=sr_1_1_sspa?dib=eyJ2IjoiMSJ9.FmD0VbTCaTkt1T0GWjF9bV9JG8X8vsO9mOXf1xuNFH8GM1jsIB9IboaQEQQBGJYV_o_nruq-GD0QXa6UOZwTpk1x_ISqW9uOD5XoQcFwm3mmgmOJG--qv3qo5MKNzVE4aKtjwEgZcZwB_d7hWTgk11_JJaqLFd1ouFBFoU8aMUWHaEGBbj5TtX4T6Z_8UMSFS4H1lh2WF5LRprjLkSLUMF656W-kCM4MGU5xLU5npMw.oUFW_sOLeWrhVW0VapPsGa03-dpdq8k5rL4asCbLmDs&dib_tag=se&keywords=detch+usb+to+ttl+serial+cable&qid=1740167263&sr=8-1-spons&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&psc=1))
>[!NOTE]
>The USB to TTL Serial 3.3V Adapter Cable may require you to install a specific driver onto your host machine. The example cable linked above requires a [PL2303 driver](https://www.prolific.com.tw/us/showproduct.aspx?p_id=225&pcid=41).
* 1x Ethernet Cable (and a local router/switch with Internet connectivity)
* (Optional) WiFi Network SSID and Password (more configuration is required for this method)

# 3. Hardware Setup
See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/OSM-93-connections.png">
</details>

1. (Optional) Connect an Ethernet cable from your LAN (router/switch) to the "ETH_A" port on the board.
2. Connect a USB-C cable from a 5V power souce (such as your host machine) to the "POWER/USB_A" port on your board.
3. Connect your USB to TTL Serial 3.3V Adapter Cable to the appropriate pins on the A55 debug header.
>[!NOTE]
>The A55 debug header is the **lower** row of 3 pins, the upper row should be left open.

>[!IMPORTANT]
>When connecting the wires of your USB to TTL Serial 3.3V Adapter Cable, the "TXD" pin of the board should connect to the "RXD" wire of your cable. Similarly, the "RXD" pin of the board should connect to the "TXD" wire of your cable. "GND" connects to "GND".

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
7. Run these commands to create and move into a directory for your demo files:
   ```
   mkdir /home/weston/demo
   cd /home/weston/demo
   ```
>[!TIP]
>To gain access to "copy" and "paste" functions inside of a Putty terminal window, you can CTRL+RIGHTCLICK within the window to utilize a dropdown menu with these commands. This is very helpful for copying/pasting between your borswer and the terminal.

8. Run this command to install the /IOTCONNECT Python Lite SDK:
   ```
   python3 -m pip install iotconnect-sdk-lite
   ```
9. Run this command to download and run the Quickstart setup script:
   ```
   curl -sOJ 'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk/refs/heads/main/scripts/quickstart.sh' && bash ./quickstart.sh
   ```

>[!IMPORTANT]
>The device template upload step of the quickstart script can be skipped since it was already taken care of in Step 5.

>[!NOTE]
>This script primarily covers device and certificate creation in /IOTCONNECT. It will require some copy/paste between your browser and the terminal window.

# 7. Using the Demo
1. Move into the correct directory and run the basic demo with these commands (can be copy and pasted as one):
```
cd /home/weston/demo
python3 /home/weston/demo/quickstart.py
```
2. View the dummy telemetry data under the "Live Data" tab for your device on /IOTCONNECT.

# 8. Resources
* [Purchase the TRIA Maaxboard OSM93](https://www.avnet.com/wps/portal/us/products/avnet-boards/avnet-board-families/maaxboard/maaxboard-osm93/?srsltid=AfmBOooL0Urtjf-giP8lPzs6dEfdVctJvArptaDqgqr9XMGEeMTIqkF_)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
