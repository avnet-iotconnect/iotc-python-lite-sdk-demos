# Microchip SAMA5D27 Quickstart

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [/IOTCONNECT: Cloud Account Setup](#4-iotconnect-cloud-account-setup)
5. [Device Setup](#5-device-setup)
6. [Using the Demo](#6-using-the-demo)
7. [Resources](#8-resources)


# 1. Introduction
This guide provides step-by-step instructions to set up the **Microchip SAMA5D27 hardware** and integrate it with **/IOTCONNECT**, Avnet's robust IoT platform. The SAMA5D27 hardware platform provides flexible options for IoT application development, enabling secure device onboarding, telemetry collection, and over-the-air (OTA) updates.

<table>
  <tr>
    <td><img src=".//media/sama5d27-product.png" width="6000"></td>
    <td>The SAMA5D27 hardware platform is based on the **Microchip SAMA5D27 System on Module (SOM)**, providing robust performance for IoT applications. Paired with **/IOTCONNECT**, this platform enables secure connectivity, real-time data collection, and device management for various use cases, including industrial automation, healthcare, and smart home solutions.</td>
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
5. Run these commands to update the core board packages and install necessary /IOTCONNECT packages:
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
python3 -m pip install requests
```
6. Then run these commands to create and move into a directory for your demo files:
```
mkdir /home/weston/demo
```
```
cd /home/weston/demo
```

>[!TIP]
>To gain access to "copy" and "paste" functions inside of a Putty terminal window, you can CTRL+RIGHTCLICK within the window to utilize a dropdown menu with these commands. This is very helpful for copying/pasting between your borswer and the terminal.

From here, to onboard your device into /IOTCONNECT you have two options. 

Option A is more automated but currently requires a Solution Key that must be requested from Avnet.

Option B is more manual but does not have that potential Solution Key obstacle.

## Option A: Onboard Device via REST API (Requires Solution Key)
1. Run this command to install the /IOTCONNECT REST API python module:
```
python3 -m pip install iotconnect-rest-api
```
2. Now run this command to protect your /IOTCONNECT credentials:
```
export HISTCONTROL=ignoreboth
```
3. Then run this /IOTCONNECT REST API CLI command (with your credentials substituted in) to log into your /IOTCONNECT account on the device:
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

4. Lastly, run this command to download and run the device setup script:
```
curl -sOJ 'https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/scripts/device-setup.py' && python3 device-setup.py
```
## Option B: Onboard Device via Online /IOTCONNECT Platform
1. In a web browser, navigate to console.iotconnect.io and log into your account.
2. In the blue toolbar on the left edge of the page, hover over the "processor" icon and then in the resulting dropdown select "Device."
3. Now in the resulting Device page, click on the "Templates" tab of the blue toolbar at the bottom of the screen.
4. Right-click and then click "save link as" on [this link to the default device template](https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/templates/plitedemo-template.json) to download the raw template file.
5. Back in the /IOTCONNECT browser tab, click on the "Create Template" button in the top-right of the screen.
6. Click on the "Import" button in the top-right of the resulting screen.
7. Select your downloaded copy of the plitedemo template from sub-step 4 and then click "save".
8. Click on the "Devices" tab of the blue toolbar at the bottom of the screen.
9. In the resulting page, click on the "Create Device" button in the top-right of the screen.
10. Customize the "Unique ID" and "Device Name" fields to your needs.
11. Select the most appropriate option for your device from the "Entity" dropdown (only for organization, does not affect connectivity).
12. Select "plitedemo" from the "Template" dropdown.
13. In the resulting "Device Certificate" field, make sure "Auto-generated" is selected.
14. Click the "Save and View" buton to go to the page for your new device.
15. Click on "Connection Info" on the right side of the device page above the processor icon.
16. In the resulting pop-up, click on the yellow/green certificate icon to download a zip file containing your device's certificates, and then close the pop-up.
17. Extract the zip folder and then rename the ```.pem``` file to ```device-pkey.pem``` and the ```.crt``` file to ```device-cert.crt```.
18. Still on your host machine, use this command within the unzipped certificates folder to convert the ```.crt``` file to another ```.pem``` file (application is expecting ```.pem``` files):
```
openssl x509 -in device-cert.crt -out device-cert.pem -outform PEM
```
>[!NOTE]
>If you are using a Windows host machine, this command is most easily performed via Git Bash. Using CMD or Powershell may require additional configuration of openssl.
    
19. Back in your device's page in /IOTCONNECT, click on the black/white/green paper-and-cog icon in the top-right of the device page (just above "Connection Info") to download your device's configuration file.
20. Using SCP (or WinSCP) copy these 3 files into the ```/home/weston/demo``` directory of your board:
    * device-cert.pem
    * device-pkey.pem
    * iotcDeviceConfig.json
      
>[!IMPORTANT]
>These files must be copied **individually** into the ```/home/weston/demo``` directory. They cannot be wrapped inside of another folder.

21. In the terminal of your board, navigate to the ```/home/weston/demo``` directory and then run this command to download the basic quickstart /IOTCONNECT application called ```app.py```:
```
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/stm32mp157f-dk2/starter-demo/src/app.py -O app.py
```
    
# 6. Using the Demo
After the device setup is complete, you can run the example /IOTCONNECT script with these commands:
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
