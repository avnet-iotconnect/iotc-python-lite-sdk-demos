# Creating and Deploying an OTA Update for IoTConnect Python Lite Demos

## Introduction
This document will help you create and deploy an OTA package for any IoTConnect Python Lite SDK Demo.

An OTA update can do any/all of the following:
* Update existing demo files
* Update certificates
* Add new files to a demo (such as new AI models)
* Re-install the IoTConnect Python Lite SDK with the newest available version.

## 1. Clone This Git Repository to Your Host Machine
Clone a copy of this repo to your local PC. This is where you will make changes/additions to the demo files.
>[!NOTE]
>On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 2. Modify and Add Files
After navigating into the "core-files" directory for your demo, modify any of the the files as desired. 

You can add additional files to your demo (such as AI models or replacement certificates) by adding them to the "additional-files" directory.

You are also able to modify the ota-install.sh script (located in the "ota" directory) to choose whether or not you want the OTA update to automatically re-install the IoTConnect Python Lite SDK with the newest available version. To do this, open ota-install.sh inside of your text editor and find this section of the script:

```
# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
# python3 -m pip install --force-reinstall iotconnect-sdk-lite
# --------------------------------------------------------------------
```
By default, the script **will not** re-install the SDK. To enable the re-install, simply backspace the "# " (remove the space as well to align the command) and then save the file.

A modified version that **will** re-install the SDK will look like this:
```
# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
python3 -m pip install --force-reinstall iotconnect-sdk-lite
# --------------------------------------------------------------------
```

## 3. Create OTA Package
Within the "core-files" directory for your demo, run these commands:
```
sudo chmod +x package-creation.sh
./package-creation.sh
```
You now have an OTA package file called "ota-package.tar.gz"

## 4. Create Firmware in IoTConnect
1) In the "Device" Page of IoTConnect, on the blue toolbar at the bottom of the page select "Firmware"
2) If a firmware has already been created for your device's template, skip to step 3. Otherwise:
   * Select the blue "Create Firmware" button in the top-right of the screen
   * Name your firmware (remember this name for later)
   * Select your device's template from the "Template" drop-down (if your device's template is not in the list, a firmware for it already exists in your IoTConnect instance)
   * Enter hardware and software version numbers (can be arbitrary such as 0, 0)
   * Select the "Browse" button in the "File" section and select your ota-package.tar.gz
   * Add descriptions if you desire
   * Select the "Save" button
3) Navigate back to the Firmware page and find your new firmware name in the list
4) Under the "Draft" column within the "Software Upgrades" column, click on the draft number (will be "1" for newly-created firmwares)
5) Select the black square with the black arrow under "Actions" to publish your firmware and make it available for OTA

## 5. Launch IoTConnect Program on Device
For your board to receive the OTA update, it must be actively connected to IoTConnect. Do this by running the main IoTConnect program. For a board running the basic quickstart IoTConnect program, the required commands are:
```
cd /home/weston
python3 quickstart.py
```

## 6. Send OTA Package
* In the "Firmware" page of IoTConnect, select the "OTA Updates" button in the top-right of the screen
* For "Hardware Version" select your firmware's name with the hyphenated hardware version from the drop-down
* Select the software version you chose for your firmware
* For "Target" select "Devices" from the drop-down
* Select your device's unique ID from the "Devices" drop-down
* Click the blue "Update" button to initialize the OTA update

## 7. View Update Reception in Device Console
Shortly after sending the OTA update, you should see an interruption in the telemetry printout on the console of your device informing you that an OTA package was received, downloaded and executed. Additionally, the program is designed to re-start itself after the OTA files have been automatically decompressed and moved to their respective destinations. There is no need for you to do any manual reboots or file manipulation. Your OTA update is complete and the program is already working again!

