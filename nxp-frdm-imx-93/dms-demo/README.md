# Upgrading from Basic Demo to EIQ Vision AI Driver Monitoring System (DMS) Demo
This guide will help you upgrade the basic IoTConnect Quickstart Demo (random-integer telemetry) to the Driver Monitoring System AI Demo with a single OTA update. The resulting demo will run default model files. After completing the steps in this guide, if you want to modify the demo to include custom model files, check out [this other guide](./UPDATE-MODELS.md).

>[!IMPORTANT]
> If you have not yet followed the [IoTConnect quickstart guide for this board](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/nxp-frdm-imx-93/README.md), complete that first and then return here to pick up on Step 1

## 1. Clone This Git Repository to Your Host Machine
Clone a copy of this repo to your local PC. This is where you will make changes/additions to the demo files.
>[!NOTE]
>On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 2. Arrange Files and Create OTA Payload
Inside of the cloned repo, navigate to the ```scripts``` folder in this directory:
```
cd ./nxp-frdm-imx-93/dms-demo/scripts
```
Then run these commands to move the Driver Monitoring System AI Demo files into the correct folder for creating an OTA upgrade package, and then navigate to that folder:
```
bash ./move-upgrade-files.sh
cd ../../../files/ota-files
```
If you wish to force-reinstall the IoTConnect Python Lite SDK on the board, modify ``install.sh`` to remove the ```#``` from line 7.

Then you can run this commands to create the compressed OTA package:
```
bash ./generate-payload.sh
```
Inside of the ```ota-files``` directory you should now see a file called ```ota-payload.tar.gz```

## 3. Launch IoTConnect Program on Device
For your board to receive the OTA update, it must be actively connected to IoTConnect. If it is not already, do this by running the main IoTConnect program on your board called "app.py":

```
cd /home/weston/demo
python3 app.py
```

From here, you have the option to push the OTA update to your devices directly from you host machine's console (see step 4A) or you can upload the OTA payload to the online IoTConnect platform and push an OTA update from there (see step 4B).

## 4A. Push OTA Update From Host Machine Console
Pushing an OTA update from your local machine requires you to be logged into your IoTConnect account so it can utilize the IoTConnect REST API.

First make sure you install the IoTConnect REST API Python module to your host machine:
```
python3 -m pip install iotconnect-rest-api
```

Run this command to protect your IoTConnect credentials:
```
export HISTCONTROL=ignoreboth
```
Then run this IoTConnect REST API CLI command (with your credentials substituted in) to log into your IoTConnect account on the device:
```
iotconnect-cli configure -u my@email.com -p "MyPassword" --pf mypf --env myenv --skey=mysolutionkey
```
For example if these were your credentials:
* Email: john.doe@gmail.com
* Password: Abc123!
* Platform: aws
* Environment: technology
* Solution Key: AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
     
Your login command would be:
```
iotconnect-cli configure -u john.doe@gmail.com -p "Abc123!" --pf aws --env technology --skey=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```
>[!IMPORTANT]
>Notice that the password argument of the command is **the only arugment that is in quotes.** Make sure you pay attention to this detail. 

You will see this output in the console if your login succeeded:
```
Logged in successfully.
```

Navigate into the "ota-files" directory of you cloned repo (same place as "core-files" and "additional-files") and run this command:
```
python3 ota-update.py
```
You will be prompted to enter the unique ID of your device, and then asked if there are other devices this OTA should be sent to as well. 

You will then be notified that the template for your device is "plitedemo" and asked if you want to change it. Respond "Y" and then after the resulting prompt enter the template code ```eiqIOTC```

You may get a notification that the eiqIOTC template already has firmware on your entity, and that an upgrade will be created for it. No action needs to be taken by you.

You should see this output when the OTA upgrade has been pushed:
```
Successful OTA push!
```

## 4B. Upload/Push OTA Update in IoTConnect Online Platform
1) In the "Device" Page of the online IoTConnect platform, on the blue toolbar at the bottom of the page select "Firmware"
2) If a firmware has already been created for the eiqIOTC template, skip to step 3. Otherwise:
   * Select the blue "Create Firmware" button in the top-right of the screen
   * Name your firmware (remember this name for later)
   * Select eiqIOTC from the "Template" drop-down (if eiqIOTC is not in the list, a firmware for it already exists in your IoTConnect instance)
   * Enter hardware and software version numbers (can be arbitrary such as 0, 0)
   * Select the "Browse" button in the "File" section and select your ota-payload.tar.gz
   * Add descriptions if you desire
   * Select the "Save" button
3) Navigate back to the Firmware page and find your new firmware name in the list
4) Under the "Draft" column within the "Software Upgrades" column, click on the draft number (will be "1" for newly-created firmwares)
5) Select the black square with the black arrow under "Actions" to publish your firmware and make it available for OTA
6) In the "Firmware" page of IoTConnect, select the "OTA Updates" button in the top-right of the screen
7) For "Hardware Version" select your firmware's name with the hyphenated hardware version from the drop-down
8) Select the software version you chose for your firmware
9) For "Target" select "Devices" from the drop-down
10) Select the unique ID(s) for your device(s) from the "Devices" drop-down
11) Click the blue "Update" button to initialize the OTA update

## 5. View Update in Device Console
Shortly after sending the OTA update via either method, you should see an interruption in the telemetry printout on the console of your device informing you that an OTA package was received, downloaded and executed. 

Additionally, the program is designed to re-start itself after the OTA files have been automatically decompressed and moved to their respective destinations via the "install.sh" script included in the package. There is no need for you to do any manual reboots or file manipulation. Your OTA update is complete and the new version of the program is already working!

Steps 6 and 7 will walk you through setting up and using a dashboard for this demo on the online IoTConnect platform.

## 6. Import Dashboard Template

* Download the demo [Dashboard Template](templates/FRDM_i.MX_93_DSM_Demo_dashboard_template.json?raw=1) (**must** Right-Click, Save As)
* **Download** the template then select `Create Dashboard` from the top of the page
* **Select** the `Import Dashboard` option and click `browse` to select the template you just downloaded.
* **Select** `eiqIOTC` for **template** and `FRDMiMX93` for **device** 
* **Enter** a name (such as `FRDM i.MX 93 DSM Demo`) and click `Save` to complete the import

## 7. Using the Dashboard

The Driver Safety Monitor demo solution will look for a variety of facial attributes from the webcam and interpret attentiveness.
<details>
<summary>Table of Supported DSM Attributes</summary>
<img src="../media/dsm_metrics.png" width="1000">
</details>

>[!TIP]
>You can find this slide and others on the demo in the [Webinar Slides](../Avnet-NXP-iMX93-EdgeAI-Webinar-Feb2025.pdf)

