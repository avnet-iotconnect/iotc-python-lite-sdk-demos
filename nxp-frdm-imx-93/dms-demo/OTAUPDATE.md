# Introduction
This document will help you create and deploy an OTA package for the FRDM i.MX 93 Development Board's DMS IoTConnect Demo. Via this OTA, you can automatically update the:
* Main IoTConnect program (imx93-ai-demo.py)
* Auxiliary AI DMS processing program (dms-processing.py)
* Automatic Model Downloading program (download_models.py)
* TFLITE models used by the AI program

The OTA update will also re-install the IoTConnect Python Lite SDK with the newest available version.

# Clone This Git Repository to Your Host Machine
Clone a copy of this repo to your local PC so you can make changes to your desired files. 
>[!NOTE]
>On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

# Modify Files and Add Models
These key files are able to be updated through the OTA process:
* imx93-ai-demo.py  (.../iotc-python-lite-sdk-demos/nxp-frdm-imx-93/dms-demo/imx93-ai-demo.py)
* dms-processing.py  (.../iotc-python-lite-sdk-demos/nxp-frdm-imx-93/dms-demo/dms-processing.py)
* download_models.py  (.../iotc-python-lite-sdk-demos/nxp-frdm-imx-93/dms-demo/dms-processing.py)

You can also add compatible TFLITE models to the demo by adding them to the ".../iotc-python-lite-sdk-demos/nxp-frdm-imx-93/dms-demo/additional-models/" directory.

>[!NOTE]
>To have the demo actually utilize your additional/replacement models, you will need to modify the corresponding model filename(s) in dms-processing.py (lines 349-351) 

# Create OTA Package
Within the cloned repository, navigate to to the directory ".../iotc-python-lite-sdk-demos/nxp-frdm-imx-93/dms-demo/scripts" and run these commands:
```
sudo chmod +x package-creation.sh
./package-creation.sh
```
You now have an OTA package file called "ota-package.tar.gz"

# Create Firmware in IoTConnect
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

# Launch IoTConnect Program on Device
For your board to receive the OTA update, it must be actively connected to IoTConnect. Do this by running the main IoTConnect program on the board:
```
cd /home/weston
python3 imx93-ai-demo.py
```

# Send OTA Package
* Back in the "Firmware" page of IoTConnect, select the "OTA Updates" button in the top-right of the screen
* For "Hardware Version" select your firmware's name with the hyphenated hardware version from the drop-down
* Select the software version you chose for your firmware
* For "Target" select "Devices" from the drop-down
* Select your device's unique ID from the "Devices" drop-down
* Click the blue "Update" button to initialize the OTA update

# View Update Reception in Device Console
Shortly after sending the OTA update, you should see an interruption in the telemetry printout on the console of your device informing you that an OTA package was received, downloaded and executed. Additionally, the program is designed to re-start itself after the OTA files have been automatically decompressed and moved to their respective destinations. There is no need for you to do any manual reboots or file manipulation. Your OTA update is complete and the program is already working again!
