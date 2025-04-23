# Microchip SAMA5D27 Quickstart

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [/IOTCONNECT: Cloud Account Setup](#4-iotconnect-cloud-account-setup)
5. [Device Setup](#5-device-setup)
6. [Using the Demo](#6-using-the-demo)
7. [Resources](#8-resources)


# 1. Introduction
This guide provides step-by-step instructions to set up the **Microchip SAMA5D27 hardware** and integrate it with **IoTConnect**, Avnet's robust IoT platform. The SAMA5D27 hardware platform provides flexible options for IoT application development, enabling secure device onboarding, telemetry collection, and over-the-air (OTA) updates.

<table>
  <tr>
    <td><img src=".//media/sama5d27-product.png" width="6000"></td>
    <td>The SAMA5D27 hardware platform is based on the **Microchip SAMA5D27 System on Module (SOM)**, providing robust performance for IoT applications. Paired with **IoTConnect**, this platform enables secure connectivity, real-time data collection, and device management for various use cases, including industrial automation, healthcare, and smart home solutions.</td>
  </tr>
</table>

# 2. Requirements
This guide has been written and tested to work on a Windows 10/11 PC. However, there is no reason this can't be replicated in other environments.

## Hardware 
* Microchip ATSAMA5D27-SOM1-EK [Purchase](https://www.avnet.com/shop/us/products/microchip/atsama5d27-som1-ek-3074457345633909354/?srsltid=AfmBOorYtSqVK7BDtS-_h4NDc21QKb7yCg1XAcTrRP8ydEuLJZFjeglj) | [User Manual & Kit Contents](https://onlinedocs.microchip.com/oxy/GUID-4F28D8A1-1A8D-4973-B7C3-4F63D191E011-en-US-4/index.html) | [All Resources](https://www.microchip.com/en-us/development-tool/atsama5d27-som1-ek1)
* Ethernet Cable
* Micro-USB Cable (included in kit)
* Standard SD Card (or micro-SD Card with Standard-Size Adapter)

## Software
* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases) or [PuTTY](https://www.putty.org/)
* Flash Yocto Image to SD Card:
  1. [Click here](https://www.linux4sam.org/bin/view/Linux4SAM/Sama5d27Som1EKMainPage#eMMC_support_on_SDMMC0) to get to the page to download the latest image for the SAMA5D27.
  2. Download the image (link may have updated name that slightly differs from screenshot):

    <img src=".//media/image-download.png" alt="Yocto Image Download"/>

  3. Follow the "Create a SD card with the demo" section of the instructions to flash the image to an SD card.


# 3. Hardware Setup
See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/sama5d27_board_setup.png" width="600">
</details>

Using the above image as reference, make the following connections:
1. Connect the included micro-USB cable from your PC to the connector labeled **#1**.
2. Connect an Ethernet cable from your LAN (router/switch) to the Ethernet connector labeled **#2**.
3. Insert the SD card (or micro-SD card with an adapter) into the slot labeled **#3**.

# 4. /IOTCONNECT: Cloud Account Setup
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
3. Noting the COM port value for "JLink CDC UART Port" in the Device Manager list, attempt to connect to your board via the terminal emulator
>[!NOTE]
>A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.
4. When prompted for a login, type `root` followed by the ENTER key.
5. Run these commands to update the core board packages and install necessary IoTConnect packages:
```
sudo apt-get update
```
```
sudo apt-get install python3-pip -y
```
```
python3 -m pip install iotconnect-sdk-lite
```
```
python3 -m pip install iotconnect-rest-api
```
6. Run these commands to create and move into a directory for your demo files:
```
mkdir /home/weston/demo
```
```
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
curl -sOJ 'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/scripts/device-setup.py' && python3 device-setup.py
```

# 6. Using the Demo
After the quickstart script is complete, you can run the example IoTConnect script with these commands:
```
cd /home/weston/demo
python3 app.py
```

The random-integer telemetry data can be viewed and verified under the "Live Data" tab for your device on /IOTCONNECT.

# 7. Resources
* [Purchase the Microchip SAMA5D27](https://www.avnet.com/shop/us/products/microchip/atsama5d27-som1-ek-3074457345633909354/?srsltid=AfmBOorYtSqVK7BDtS-_h4NDc21QKb7yCg1XAcTrRP8ydEuLJZFjeglj)
* [More /IOTCONNECT Microchip Guides](https://avnet-iotconnect.github.io/partners/microchip/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
