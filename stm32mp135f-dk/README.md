# STM32MP135F-DK QuickStart

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [/IOTCONNECT: Cloud Account Setup](#4-iotconnect-cloud-account-setup)
5. [/IOTCONNECT: Device Template Setup](#5-iotconnect-device-template-setup)
6. [Device Software Setup](#6-device-software-setup)
7. [Start the Application and Verify Data](#7-start-the-application-and-verify-data)
8. [Troubleshooting](#8-troubleshooting)
9. [Resources](#9-resources)

# 1. Introduction
This guide is designed to walk through the steps to connect the STM32MP135F-DK to the Avnet /IOTCONNECT platform and periodically send general telemetry data.

<table>
  <tr>
    <td><img src="./media/mp135-product.png" width="6000"></td>
    <td>The STM32MP135 Discovery kit (STM32MP135F-DK) leverages the capabilities of the 1 GHz STM32MP135 microprocessors to allow users to develop easily applications using STM32 MPU OpenSTLinux Distribution software. It includes an ST-LINK embedded debug tool, LEDs, push-buttons, two 10/100 Mbit/s Ethernet (RMII) connectors, one USB Type-C® connector, four USB Host Type-A connectors, and one microSD™ connector. To expand the functionality of the STM32MP135 Discovery kit, one GPIO expansion connector is also available for third-party shields.
Additionally, the STM32MP135 Discovery kit features an LCD display with a touch panel, Wi‑Fi® and Bluetooth® Low Energy capability, and a 2-megapixel CMOS camera module.
It also provides secure boot and cryptography features.</td>
  </tr>
</table>

# 2. Requirements
This guide has been written and tested to work on a Windows 10/11 PC. However, there is no reason this can't be replicated in other environments.

## Hardware 
* STM32MP135F-DK [Purchase](https://www.avnet.com/shop/us/products/stmicroelectronics/stm32mp135f-dk-3074457345651659229/?srsltid=AfmBOopijKmQ00ko1YYwjONN5cRH9akfAf_aqdRSphwy7iE1XhpDUiG0) | [User Manual & Kit Contents](https://www.st.com/resource/en/user_manual/um2993-discovery-kit-with-1-ghz-stm32mp135fa-mpu-stmicroelectronics.pdf) | [All Resources](https://www.st.com/en/evaluation-tools/stm32mp135f-dk.html)
* 1 USB Type-C Cable
* 1 Micro-USB Cable
* Ethernet Cable
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
2. Connect the USB-C cable from a 5V/2.4A (up to 3A) power supply to the PWR USB-C connector on the board, labeled **#2**.
3. Connect the Micro-USB cable from your PC to the Micro-USB connector labeled **#3** on the reference image.

# 4. /IOTCONNECT: Cloud Account Setup
An /IOTCONNECT account with AWS backend is required.  If you need to create an account, a free trial subscription is available.
The free subscription may be obtained directly from iotconnect.io or through the AWS Marketplace.


* Option #1 (Recommended) [/IOTCONNECT via AWS Marketplace](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/iotconnect_aws_marketplace.md) - 60 day trial; AWS account creation required
* Option #2 [/IOTCONNECT via iotconnect.io](https://subscription.iotconnect.io/subscribe?cloud=aws) - 30 day trial; no credit card required



> [!NOTE]
> Be sure to check any SPAM folder for the temporary password after registering.

# 5. /IOTCONNECT: Device Template Setup
A Device Template defines the type of telemetry the platform should expect to receive.
* Download the pre-made [Device Template](https://github.com/avnet-iotconnect/iotc-python-lite-sdk/blob/main/files/plitedemo-template.json?raw=1) (**MUST** Right-Click and "Save-As" to get the raw json file)
* Import the template into your /IOTCONNECT instance. (A guide on [Importing a Device Template](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/import_device_template.md) is available.)

# 6. Device Software Setup
1. Open a serial terminal emulator program such as TeraTerm.
2. Ensure that your serial settings in your terminal emulator are set to:
  - Baud Rate: 115200
  - Data Bits: 8
  - Stop Bits: 1
  - Parity: None
3. Noting the COM port value for "STMicroelectronics STLink Virtual COM Port" in the Device Manager list, attempt to connect to your board via the terminal emulator
>[!NOTE]
>A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.
4. When prompted for a login, type `root` followed by the ENTER key.
5. Execute system updates and install the IoTConnect Python Lite SDK with these commands:
```
sudo apt-get update
sudo apt-get install python3-pip -y
python3 -m pip install iotconnect-sdk-lite
```
6. Navigate to the proper directory and then run download and run the quickstart script with these commands:
```
cd /home/weston
curl -sOJ 'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk/refs/heads/main/scripts/quickstart.sh' && bash ./quickstart.sh
```

# 7. Start the Application and Verify Data
After the quickstart script is complete, you can run the example IoTConnect script with these commands:
```
cd /home/weston
python3 quickstart.py
```

The random-integer telemetry data can be viewed and verified under the "Live Data" tab for your device on /IOTCONNECT.

# 8. Troubleshooting

To return the board to an out-of-box state, refer to the [FLASHING.md](FLASHING.md) guide.

# 9. Resources
* [Purchase the STM32MP135F-DK](https://www.avnet.com/shop/us/products/stmicroelectronics/stm32mp135f-dk-3074457345659849803/?srsltid=AfmBOopquBKia0rOHMSNs21TNvnk7RXm224OmsFITHs0A9LhuKjX4zHK)
* [More /IOTCONNECT ST Guides](https://avnet-iotconnect.github.io/partners/st/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
