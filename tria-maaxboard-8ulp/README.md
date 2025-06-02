# TRIA MaaXBoard 8ULP QuickStart

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Hardware Setup](#3-hardware-setup)
4. [Cloud Account Setup](#4-cloud-account-setup)
5. [Device Setup](#5-device-setup)
6. [Using the Demo](#6-using-the-demo)
7. [Resources](#7-resources)

# 1. Introduction
This guide is designed to walk through the steps to connect the TRIA MaaXBoard 8ULP to the Avnet /IOTCONNECT platform and demonstrate the standard IoT function of telemetry collection.

<table>
  <tr>
    <td><img src="./media/8ulp-product-image.jpg" width="6000"></td>
    <td>MaaXBoard 8ULP features the NXP i.MX 8ULP processor to achieve ultra-low power, EdgeLock® secured intelligent edge applications. The i.MX 8ULP device is architected with 3 separate processing domains:

* The application domain includes two Arm® Cortex®-A35 (800 MHz) cores plus 3D/2D GPUs for GUI-enabled Linux applications.
* The Real Time domain includes an Arm Cortex-M33 (216 MHz) core, plus Fusion DSP (200 MHz) core for low-power audio/voice use cases.
* The LPAV domain (Low Power Audio Video) has a HiFi 4 DSP (475 MHz) core to support advanced audio, ML and sensor applications.</td>
  </tr>
</table>

# 2. Requirements

## Hardware
* TRIA MaaXBoard 8ULP [Purchase](https://www.avnet.com/shop/us/products/avnet-engineering-services/aes-maaxb-8ulp-sk-g-3074457345648110677/) | [User Manual](https://www.avnet.com/wps/wcm/connect/onesite/60e2bb73-e479-4f76-821f-0b811ae52643/MaaXBoard-8ULP-User-Guide-v1.0.pdf?MOD=AJPERES&CACHEID=ROOTWORKSPACE.Z18_NA5A1I41L0ICD0ABNDMDDG0000-60e2bb73-e479-4f76-821f-0b811ae52643-oHYri7w) | [All Resources](https://www.avnet.com/wps/portal/us/products/avnet-boards/avnet-board-families/maaxboard/maaxboard-8ulp/?srsltid=AfmBOorNz2jO8e5kEJa7Yn3Qh_B-iuEQiawLVqTFyOsdT7U1ry41Dt_b)
* 2x USB Type-C Cables
* 1x Ethernet Cable (and a local router/switch with Internet connectivity)

## Software
* A serial terminal such as [TeraTerm](https://github.com/TeraTermProject/teraterm/releases) or [PuTTY](https://www.putty.org/)

# 3. Hardware Setup
See the reference image below for cable connections.
<details>
<summary>Reference Image with Connections</summary>
<img src="./media/8ulp_board_setup.png">
</details>

1. Connect an Ethernet cable from your LAN (router/switch) to the "ETH_A" port on the board.
2. Connect a USB-C cable from a 5V power souce (such as your host machine) to the "USB0/POWER" port on your board.
3. Connect a USB-C cable from your host machine to the "Debug" port for connection to the console.

# 4. Cloud Account Setup
An /IOTCONNECT account with AWS backend is required.  If you need to create an account, a free trial subscription is available.

[/IOTCONNECT Free Trial (AWS Version)](https://subscription.iotconnect.io/subscribe?cloud=aws)

> [!NOTE]
> Be sure to check any SPAM folder for the temporary password after registering.

See the /IOTCONNECT [Subscription Information](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/subscription.md) for more details on the trial.

# 5. Device Setup
1. With the board powered on and connected to your host machine, open your Device Manager and note the COM ports that are in use by a "USB Serial Port" (should be 4 of them). You will use the **2nd-highest port number**. For example, if the 4 ports listed are COM46, COM47, COM48, and COM49, you will connect to COM48.
2. Open a terminal emulator program such as TeraTerm or PuTTY on your host machine.
3. Ensure that your serial settings in your terminal emulator are set to:
  - Baud Rate: 115200
  - Data Bits: 8
  - Stop Bits: 1
  - Parity: None
4. Connect to the port specified from sub-step 1 (2nd-highest port number)

>[!NOTE]
>A successful connection may result in just a blank terminal box. If you see a blank terminal box, press the ENTER key to get a login prompt. An unsuccessful connection attempt will usually result in an error window popping up.

5. When prompted for a login, type `root` followed by the ENTER key.
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
* [Purchase the TRIA MaaXBoard 8ULP](https://www.avnet.com/shop/us/products/avnet-engineering-services/aes-maaxb-8ulp-sk-g-3074457345648110677/)
* [/IOTCONNECT Overview](https://www.iotconnect.io/)
* [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
