# Updating/Adding TFLITE Models to EIQ Vision AI Driver Monitoring System (DMS) Demo
This guide will help you upgrade the basic IoTConnect Quickstart Demo (random-integer telemetry) to the Driver Monitoring System AI Demo with a single OTA update. The resulting demo will run default model files. After completing the steps in this guide, if you want to modify the demo to include custom model files, check out [this other guide].

>[!IMPORTANT]
> If you have not yet followed the [IoTConnect quickstart guide for this board](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/nxp-frdm-imx-93/README.md) and followed [the guide to upgrade to the EIQ Vision AI Driver Monitoring System (DMS) Demo](./README.md), complete those first and then return here to pick up on Step 1.

## 1. Clone This Git Repository to Your Host Machine
Clone a copy of this repo to your local PC. This is where you will make changes/additions to the demo files.
>[!NOTE]
>On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 2. Add New Model Files and Move Model Update Scripts
Any new model files you wish to push to your board can be copied into the ```<your leading directories>/iotc-python-lite-sdk-demos/files/additional-files/``` folder of the cloned repo.

Navigate to the ```scripts``` folder for this demo inside of the cloned ```iotc-python-lite-sdk-demos``` repo:
```
cd ./nxp-frdm-imx-93/dms-demo/scripts
```
Then run this command to move the required files into the correct folder for creating an OTA upgrade package:
```
bash ./move-model-update-files.sh
```
## 3. Modify DMS Processing File and Install Script
For the updated demo to utilize the new TFLITE model(s) you are adding, you need to point to the new model file names in the ```dms-processing.py``` script.

First navigate to the ```core-files``` directory where ```dms-processing.py``` was just copied to:
```
cd ../../../files/core-files
```
Then make these basic modifications to ```dms-processing.py``` in a text editor:

* If using a new Face Detection model, change the filename to the filename of the new model in line 351
* If using a new Face Landmark model, change the filename to the filename of the new model in line 352
* If using a new Eye Landmark model, change the filename to the filename of the new model in line 353

Next, naviagte to the ```ota-files``` directory:
```
cd ../ota-files
```
You will need to make these slight modifications to the ```install.sh``` script for this OTA update so only the required actions are executed:

* In line 10, change the ```true``` to ```false```
* If you wish to force-reinstall the IoTConnect Python Lite SDK on the board, remove the ```#``` from line 7 as well

## 4. Create OTA Payload

Then run this command to create the compressed OTA package:
```
bash ./generate-payload.sh
```
Inside of the ```ota-files``` directory you should now see a file called ```ota-payload.tar.gz```

## 5. Launch IoTConnect Program on Device
For your board to receive the OTA update, it must be actively connected to IoTConnect. If it is not already, do this by running the main IoTConnect program on your board called "app.py":

```
cd /home/weston/demo
python3 app.py
```

From here, you have the option to push the OTA update to your devices directly from you host machine's console (see step 6A) or you can upload the OTA payload to the online IoTConnect platform and push an OTA update from there (see step 6B).

## 6A. Push OTA Update From Host Machine Console
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

## 6B. Upload/Push OTA Update in IoTConnect Online Platform
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

## 7. View Update in Device Console
Shortly after sending the OTA update via either method, you should see an interruption in the telemetry printout on the console of your device informing you that an OTA package was received, downloaded and executed. 

Additionally, the program is designed to re-start itself after the OTA files have been automatically decompressed and moved to their respective destinations via the "install.sh" script included in the package. There is no need for you to do any manual reboots or file manipulation. Your OTA update is complete and the new version of the program is already working!
