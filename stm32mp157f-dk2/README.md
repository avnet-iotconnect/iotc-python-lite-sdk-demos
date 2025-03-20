# STM32MP157F-DK2 QuickStart

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
This guide is designed to walk through the steps to connect the STM32MP157F-DK2 to the Avnet /IOTCONNECT platform and periodically send general telemetry data.

<table>
  <tr>
    <td><img src="./media/mp157-product.png" width="6000"></td>
    <td>The STM32MP157F-DK2 Discovery kit leverages the capabilities of the increased-frequency 800 MHz microprocessors in the STM32MP157 product line to allow users to develop applications easily using STM32 MPU OpenSTLinux Distribution software for the main processor and STM32CubeMP1 software for the coprocessor. It includes an ST-LINK embedded debug tool, LEDs, push-buttons, one Ethernet 1-Gbit/s connector, one USB Type-C® OTG connector, four USB Host Type-A connectors, one HDMI® transceiver, one stereo headset jack with analog microphone, and one microSD™ connector. To expand the functionality of the STM32MP157D-DK1 and STM32MP157F-DK2 Discovery kits, two GPIO expansion connectors are also available for ARDUINO® and Raspberry Pi® shields. Additionally, the STM32MP157F-DK2 Discovery kit features an LCD display with a touch panel, and Wi‑Fi® and Bluetooth® Low Energy capability.</td>
  </tr>
</table>

# 2. Requirements
This guide has been written and tested to work on a Windows 10/11 PC. However, there is no reason this can't be replicated in other environments.

## Hardware 
* STM32MP157F-DK2 [Purchase](https://www.newark.com/stmicroelectronics/stm32mp157f-dk2/discovery-kit-arm-cortex-a7-cortex/dp/14AJ2731) | [User Manual & Kit Contents](https://wiki.st.com/stm32mpu/wiki/Getting_started/STM32MP1_boards/STM32MP157x-DK2%20) | [All Resources](https://www.st.com/en/evaluation-tools/stm32mp157f-dk2.html#documentation)
* 1 USB Type-C Cable (second USB-C cable required for flashing)
* 1 Micro-USB Cable
* Ethernet Cable
* (Optional) WiFi Network SSID and Password

## Software
* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases) or [PuTTY](https://www.putty.org/)

# 3. Hardware Setup
See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/mp157f_board_setup.png" width="600">
</details>

Using the above image as reference, make the following connections:
1. (OPTIONAL) Connect an Ethernet cable from your LAN (router/switch) to the Ethernet connector labeled **#1**. If you instead wish to use Wi-Fi, after booting your board refer to the [WIFI](WIFI.md) guide.
2. Connect the USB-C cable from a 5V/2.4A (up to 3A) power supply to the "PWR_IN" USB-C connector on the board, labeled **#2**.
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
* [Purchase the STM32MP157F-DK2](https://www.newark.com/stmicroelectronics/stm32mp157f-dk2/discovery-kit-arm-cortex-a7-cortex/dp/14AJ2731)
* [More /IOTCONNECT ST Guides](https://avnet-iotconnect.github.io/partners/st/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
