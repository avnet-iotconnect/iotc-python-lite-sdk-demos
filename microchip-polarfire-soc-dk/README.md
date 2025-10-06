# Microchip PolarFire SoC Discovery Kit QuickStart

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Software Setup](#4-software-setup)
5. [/IOTCONNECT: Cloud Account Setup](#5-iotconnect-cloud-account-setup)
6. [Device Setup](#6-device-setup)
7. [Onboard Device via Online /IOTCONNECT Platform](#7-onboard-device-via-online-iotconnect-platform)
8. [Using the Demo](#8-using-the-demo)
9. [Resources](#9-resources)

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
connections via the USB type C connector. An on-board FlashPro5 programmer is available to program and debug the PolarFIre 
FPGA through USB-to-JTAG channel.</td>
  </tr>
</table>

# 2. Requirements

This guide has been written and tested to work on a Windows 10/11 PC. However, there is no reason this can't be
replicated in other environments.

## Hardware

* Microchip PolarFire SoC Discovery Kit [Purchase](https://www.avnet.com/americas/product/microchip/mpfs-disco-kit/evolve-67810612/) | [User Manual & Kit Contents](https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/PolarFire_SoC_FPGA_Discovery_Kit_User_Guide.pdf) | [All Resources](https://www.microchip.com/en-us/development-tool/mpfs-disco-kit)
* Ethernet Cable
* USB-C Cable (included in kit)
* SanDisk 8GB UHS-1 Class 10 micro-SD card (available [here](https://www.amazon.com/SanDisk-Industrial-MicroSD-SDSDQAF3-008G-I-Adapter/dp/B07BZ5SY18/ref=sr_1_4?crid=360H9A81QLNK9&dib=eyJ2IjoiMSJ9.fJWARiyPCzdh0zksHaXihTpM4ELLohYxpV4AVAFi107f7TjrzADYC7tr8UjvghCwfCAk7BLTzbgn6_jTNMDv6lSkED8zjlCYBMLxpwgqLUOmEPb0XXTc0rMbt9MHx7kkFJdKpZ_iFFE7b9XGyvPxElLRvzl7s4GYW7ThzZP2kj1-bcvZg6vp6EDKNBm5NdvW-AlQmk1BfYPHz2-6xyUgP2VTI4HknDTHhY1kUqp9JB4.hOOSnRKZmLV0wJdTT4qFKMg413rz5AnPpEFy07uLurk&dib_tag=se&keywords=sandisk+8gb+micro+sd+card&qid=1759769517&sprefix=sandisk+8gb+micro+sd+card%2Caps%2C147&sr=8-4))

> [!NOTE]
> The PolarFire SoC Discovery Kit **requires a SanDisk-brand micro-SD card**. Other brands of SD cards **will fail to boot** 
> due to specific memory-mapping requirements in the bootloader.

## Software

* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases)
  or [PuTTY](https://www.putty.org/)
* An SD-Card flashing utility such as [Balena Etcher](https://etcher.balena.io/)
* Microchip FlashPro Express
  * Download the lastest "Programming and Debug" package for your OS [from this page](https://www.microchip.com/en-us/products/fpgas-and-plds/fpga-and-soc-design-tools/programming-and-debug/lab)
and then run extract/execute the installer (may require admin/sudo privileges).


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
3. Open FlashPro Express, and start a new project. In the "Import 
FlashPro Express job file" browse section, select the downloaded .job file. For the project location, simply choose the 
same downloaded/extracted folder that contains the .job file. Select "Ok" to open the new project.
4. After the new project has loaded, click the "RUN" button to flash the board.
5. After the flash has completed, unplug and re-plug in the board to power-cycle and ensure the new programming is in effect.

## Flash Linux Image

1. Download the lastest Linux Image release for the PolarFire SoC Discovery Kit by navigating [the linux4microchip PolarFire
SoC Releases page](https://github.com/linux4microchip/meta-mchp/releases), scrolling down to the "Pre-built images for 
the Discovery Kit Reference Design" section and clicking on the "pre-built image" link. The downloaded filename should
be similar to "mchp-base-image-mpfs-disco-kit.rootfs-20250725104508.wic.gz" with only the timestamp potentially being different 
depending on what the latest release is at the time.
2. Extract the downloaded image so that you have a **.wic** file to flash. Attempting to flash the compressed .gz file 
is known to cause issues with the bootloader.
3. Use an SD-Card flashing utility such as Balena Etcher to flash the .wic image file onto your SanDisk-branded micro-SD
card.
4. After flashing, insert the micro-SD card into the micro-SD card slot on the PolarFire SoC Discovery Kit.
5. Unplug and replug the board to power-cycle it.

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

3. Check your device manager list and see that there are 3 COM port entries for your PolarFire SoC Discovery Kit. Connect 
to the **middle-numbered port.** For example, given these COM ports:

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
mkdir -p /home/weston/demo && cd /home/weston/demo
```

> [!TIP]
> To gain access to "copy" and "paste" functions inside of a Putty terminal window, you can CTRL+RIGHTCLICK within the
> window to utilize a dropdown menu with these commands. This is very helpful for copying/pasting between your browser and
> the terminal.

The next step will be to onboard your Microchip PolarFire SoC Discovery Kit into /IOTCONNECT.

# 7. Onboard Device via Online /IOTCONNECT Platform

1. In a web browser, navigate to console.iotconnect.io and log into your account.
2. In the blue toolbar on the left edge of the page, hover over the "processor" icon and then in the resulting dropdown
   select "Device."
3. Now in the resulting Device page, click on the "Templates" tab of the blue toolbar at the bottom of the screen.
4. Right-click and then click "save link as"
   on [this link to the default device template](https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/templates/plitedemo-template.json)
   to download the raw template file.
5. Back in the /IOTCONNECT browser tab, click on the "Create Template" button in the top-right of the screen.
6. Click on the "Import" button in the top-right of the resulting screen.
7. Select your downloaded copy of the plitedemo template from sub-step 4 and then click "save".
8. Click on the "Devices" tab of the blue toolbar at the bottom of the screen.
9. In the resulting page, click on the "Create Device" button in the top-right of the screen.
10. Customize the "Unique ID" and "Device Name" fields to your needs.
11. Select the most appropriate option for your device from the "Entity" dropdown (only for organization, does not
    affect connectivity).
12. Select "plitedemo" from the "Template" dropdown.
13. In the resulting "Device Certificate" field, make sure "Auto-generated" is selected.
14. Click the "Save and View" buton to go to the page for your new device.
15. Click on "Connection Info" on the right side of the device page above the processor icon.
16. In the resulting pop-up, click on the yellow/green certificate icon to download a zip file containing your device's
    certificates, and then close the pop-up.
17. Extract the zip folder and then rename the ```.pem``` file to ```device-pkey.pem``` and the ```.crt``` file to
    ```device-cert.crt```.
18. Still on your host machine, use this command within the unzipped certificates folder to convert the ```.crt``` file
    to another ```.pem``` file (application is expecting ```.pem``` files):

```
openssl x509 -in device-cert.crt -out device-cert.pem -outform PEM
```

> [!NOTE]
> If you are using a Windows host machine, this command is most easily performed via Git Bash. Using CMD or Powershell
> may require additional configuration of openssl.

19. Back in your device's page in /IOTCONNECT, click on the black/white/green paper-and-cog icon in the top-right of the
    device page (just above "Connection Info") to download your device's configuration file.
20. Using SCP (or WinSCP) copy these 3 files into the ```/home/weston/demo``` directory of your board:
    * device-cert.pem
    * device-pkey.pem
    * iotcDeviceConfig.json

> [!IMPORTANT]
> These files must be copied **individually** into the ```/home/weston/demo``` directory. They cannot be wrapped inside
> of another folder.

21. In the terminal of your board, navigate to the ```/home/weston/demo``` directory and then run this command to
    download the basic quickstart /IOTCONNECT application called ```app.py```:

```
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/stm32mp157f-dk2/starter-demo/src/app.py -O app.py
```

# 8. Using the Demo

After the device setup is complete, you can run the example /IOTCONNECT script with these commands:

```
cd /home/weston/demo
python3 app.py
```

The random-integer telemetry data can be viewed and verified under the "Live Data" tab for your device on /IOTCONNECT.

# 9. Resources

* [Purchase the Microchip PolarFire SoC Discovery Kit](https://www.avnet.com/americas/product/microchip/mpfs-disco-kit/evolve-67810612/)
* [More /IOTCONNECT Microchip Guides](https://avnet-iotconnect.github.io/partners/microchip/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
