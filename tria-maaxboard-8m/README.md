# TRIA Maaxboard 8M QuickStart

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Cloud Account Setup](#4-cloud-account-setup)
5. [Device Setup](#5-device-setup)
6. [Using the Demo](#6-using-the-demo)
7. [Resources](#7-resources)

# 1. Introduction
This guide is designed to walk through the steps to connect the TRIA Maaxboard 8ULP to the Avnet /IOTCONNECT platform and demonstrate the standard IoT function of telemetry collection.

<table>
  <tr>
    <td><img src="./media/8m-product-image.png" width="6000"></td>
    <td>MThe MaaXBoard is a low-cost, NXP i.MX 8M processor-based, single board computer ideal for embedded computing and smart edge IoT applications. The i.MX 8M family of application processors are based on the Arm® Cortex®-A53 and Cortex-M4 cores which provide industry-leading audio, voice, and video processing for applications that scale from consumer home audio to industrial building automation and embedded computers.</td>
  </tr>
</table>

# 2. Requirements

## Hardware
* TRIA Maaxboard 8M [Purchase](https://www.avnet.com/americas/products/avnet-boards/avnet-board-families/maaxboard/maaxboard/?srsltid=AfmBOoo1v6O9g0ca3zFihNOWXG8QfxUKQ-tUa7ulkIOv9Cw2jWph8f7a?srsltid=AfmBOoo1v6O9g0ca3zFihNOWXG8QfxUKQ-tUa7ulkIOv9Cw2jWph8f7a) | [User Manual](https://www.avnet.com/wcm/connect/3cb1a777-3aa8-4394-9ba8-135d9ffa1470/MaaXBoard-Linux-Yocto-UserManual-V2.1.pdf?MOD=AJPERES&CACHEID=ROOTWORKSPACE-3cb1a777-3aa8-4394-9ba8-135d9ffa1470-oPqIZjK) | [All Resources](https://www.avnet.com/americas/products/avnet-boards/avnet-board-families/maaxboard/maaxboard/?srsltid=AfmBOopeNzX_SULx91T_mZ4G3i89BZBufmM_6u_ZXKRWNVNT9a6Bm2Px?srsltid=AfmBOopeNzX_SULx91T_mZ4G3i89BZBufmM_6u_ZXKRWNVNT9a6Bm2Px)
* 1x USB Type-C Cable
* 1x USB to TTL Serial 3.3V Adapter Cable (must be purchased separately, this is [the cable used by Avnet's engineer](https://www.amazon.com/Serial-Adapter-Signal-Prolific-Windows/dp/B07R8BQYW1/ref=sr_1_1_sspa?dib=eyJ2IjoiMSJ9.FmD0VbTCaTkt1T0GWjF9bV9JG8X8vsO9mOXf1xuNFH8GM1jsIB9IboaQEQQBGJYV_o_nruq-GD0QXa6UOZwTpk1x_ISqW9uOD5XoQcFwm3mmgmOJG--qv3qo5MKNzVE4aKtjwEgZcZwB_d7hWTgk11_JJaqLFd1ouFBFoU8aMUWHaEGBbj5TtX4T6Z_8UMSFS4H1lh2WF5LRprjLkSLUMF656W-kCM4MGU5xLU5npMw.oUFW_sOLeWrhVW0VapPsGa03-dpdq8k5rL4asCbLmDs&dib_tag=se&keywords=detch+usb+to+ttl+serial+cable&qid=1740167263&sr=8-1-spons&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&psc=1))
>[!NOTE]
>The USB to TTL Serial 3.3V Adapter Cable may require you to install a specific driver onto your host machine. The example cable linked above requires a [PL2303 driver](https://www.prolific.com.tw/us/showproduct.aspx?p_id=225&pcid=41).
* Ethernet Cable **or** WiFi Network SSID and Password
* Micro-SD card (at least 8GB) and hardware to connect the Micro-SD card to your PC for image flashing

## Software
* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases) or [PuTTY](https://www.putty.org/)
  
* Flash Yocto Image to SD Card:
  1. [Click here](https://downloads.iotconnect.io/partners/nxp/disk-images/maaxboard/avnet-image-full-maaxboard-20231215021741.rootfs.zip) to download a zipped Yocto image file for the MaaXBoard
  3. Extract the zipped image file to get access to the actual ```.wic``` image file
  4. Use an SD-card flashing software such as [Balena Etcher](https://etcher.balena.io/) to flash the ```.wic``` file onto the micro-SD card
  5. After the flash is complete, insert the micro-SD card into the micro-SD card slot on the MaaXBoard until it clicks into place
  6. Power on (or reboot) the MaaXBoard with a USB-C cable and it will boot from the micro-SD card 

# 3. Hardware Setup
See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/8m-board-setup.png">
</details>

1. (OPTIONAL) Connect an ethernet cable from your LAN (router/switch) to the ethernet port on the board.
2. Connect a USB-C cable from a 5V power souce (such as your PC) to the USB-C port on your board.
3. Connect your USB to TTL Serial 3.3V Adapter Cable to the appropriate pins (see image below) on the J10 40-pin GPIO header.

<img src="./media/serial-comms-wiring.png">

>[!IMPORTANT]
>When connecting the wires of your USB to TTL Serial 3.3V Adapter Cable, the "TXD" pin of the board should connect to the "RXD" wire of your cable. Similarly, the "RXD" pin of the board should connect to the "TXD" wire of your cable. "GND" connects to "GND". In the image below, 

# 4. Cloud Account Setup
An /IOTCONNECT account with AWS backend is required.  If you need to create an account, a free trial subscription is available.

[/IOTCONNECT Free Trial (AWS Version)](https://subscription.iotconnect.io/subscribe?cloud=aws)

> [!NOTE]
> Be sure to check any SPAM folder for the temporary password after registering.

See the /IOTCONNECT [Subscription Information](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/subscription.md) for more details on the trial.

# 5. Device Setup
1. With the board powered on and connected to your host machine, open your Device Manager list and note the COM port being utilized by your adapter cable.
>[!TIP]
>If you do not see your cable in the COM port list, check for it in the "Other devices" section. You may need to install/select the driver for the cable to get it to be recognized as a COM port connection.

2. Open a terminal emulator program such as TeraTerm or PuTTY on your host machine.
3. Ensure that your serial settings in your terminal emulator are set to:
  - Baud Rate: 115200
  - Data Bits: 8
  - Stop Bits: 1
  - Parity: None
4. Use that COM port from sub-step 1 to connect to your board via the terminal emulator.

>[!NOTE]
>A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.

5. When prompted for a login, type `root` for the username. You should not be prompted for a password as long as you use the provided image.
6. Run these commands to begin to configure your board for IoTConnect:
```
sudo apt-get update
```
```
python3 -m pip install iotconnect-sdk-lite
```
```
python3 -m pip install requests
```
```
mkdir /home/weston/demo
```
```
cd /home/weston/demo
```
>[!TIP]
>To gain access to "copy" and "paste" functions inside of a PuTTY terminal window, you can CTRL+RIGHTCLICK within the window to utilize a dropdown menu with these commands. This is very helpful for copying/pasting between your borswer and the terminal.

From here, to onboard your device into IoTConnect you have two options. 

Option A is more automated but currently requires a Solution Key that must be requested from Avnet.

Option B is more manual but does not have that potential Solution Key obstacle.

## Option A: Onboard Device via REST API (Requires Solution Key)
1. Run these commands to install the IoTConnect REST API python module:
```
python3 -m pip install iotconnect-rest-api
```
2. Now run this command to protect your IoTConnect credentials:
```
export HISTCONTROL=ignoreboth
```
3. Then run this IoTConnect REST API CLI command (with your credentials substituted in) to log into your IoTConnect account on the device:
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
## Option B: Onboard Device via Online IoTConnect Platform
1. In a web browser, navigate to console.iotconnect.io and log into your account.
2. In the blue toolbar on the left edge of the page, hover over the "processor" icon and then in the resulting dropdown select "Device."
3. Now in the resulting Device page, click on the "Templates" tab of the blue toolbar at the bottom of the screen.
4. Right-click and then click "save link as" on [this link to the default device template](https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/templates/plitedemo-template.json) to download the raw template file.
5. Back in the IoTConnect browser tab, click on the "Create Template" button in the top-right of the screen.
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
    
19. Back in your device's page in IoTConnect, click on the black/white/green paper-and-cog icon in the top-right of the device page (just above "Connection Info") to download your device's configuration file.
20. Using SCP (or WinSCP) copy these 3 files into the ```/home/weston/demo``` directory of your board:
    * device-cert.pem
    * device-pkey.pem
    * iotcDeviceConfig.json
      
>[!IMPORTANT]
>These files must be copied **individually** into the ```/home/weston/demo``` directory. They cannot be wrapped inside of another folder.

21. In the terminal of your board, navigate to the ```/home/weston/demo``` directory and then run this command to download the basic quickstart IoTConnect application called ```app.py```:
```
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/stm32mp157f-dk2/starter-demo/src/app.py -O app.py
```

# 6. Using the Demo
1. Run the basic demo with this command:
```
python3 app.py
```
>[!NOTE]
>Always make sure you are in the ```/home/weston/demo``` directory before running the demo. You can move to this directory with the command: ```cd /home/weston/demo```

2. View the random-integer telemetry data under the "Live Data" tab for your device on /IOTCONNECT.

# 7. Resources
* [Purchase the TRIA Maaxboard 8ULP](https://www.avnet.com/shop/us/products/avnet-engineering-services/aes-maaxb-8ulp-sk-g-3074457345648110677/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
