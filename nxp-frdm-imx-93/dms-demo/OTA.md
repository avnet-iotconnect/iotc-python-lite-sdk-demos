# Introduction
This document will help you create and deploy an OTA package for the FRDM i.MX 93 Development Board's DMS IoTConnect Demo. Via this OTA, you can automatically update the:
* Main IoTConnect program (imx93-ai-demo.py)
* Auxiliary AI DMS processing program (dms-processing.py)
* TFLITE models used by the AI program

# Create Updated Files
The first step is to actually make your desired changes to the files. You can download copies of *imx93-ai-demo.py* and *dms-processing.py* from this repository and then make your changes on your host machine. TFLITE models can be downloaded from numerous websites, but make sure they are compatible with the DMS demo. Alternatively, for a custom application you could train your own models.
>[!IMPORTANT]
>When making changes to *imx93-ai-demo.py* and *dms-processing.py*, make sure you save them under the exact same file name as the originals. Model files can have any name as long as they have a ".tflite" file extension.

# Download OTA Package Installation Script
To automatically update *dms-processing.py* and put additional model files into the correct directory on the i.MX 93, you must include the [OTA installation script](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/nxp-frdm-imx-93/dms-demo/scripts/ota_install.sh?raw=1) (must right-click and "Save link as..." to download) in your OTA package. 

It is named "ota_install.sh"

# Gather Files and Zip OTA Package
Put your OTA files (including *imx93-ai-demo.py*, *dms-processing.py*, and TFLITE model files) all in one directory. Then zip together the individual files into a .zip file in a terminal or by selecting each of the files (CTRL+click allows you to select mutliple individual files at once) and then right-clicking and selecting your host machine's compression command in the drop-down.
>[!IMPORTANT]
>For the OTA installation to work properly, you must zip together the **individual files**. You **cannot** put the files into a folder and then zip that folder.

>[!NOTE]
>The OTA package system for the i.MX 93 currently only supports ".zip" files. **Using ".tar" or ".tar.gz" will not work**.

The name of your zipped OTA file does not matter, but should probably have a timestamp or version number in its name for your own record-keeping.

# Create Firmware in IoTConnect
1) In the "Device" Page of IoTConnect, on the blue toolbar at the bottom of the page select "Firmware"
2) If using the AWSPOC instance of IoTConnect, a firmware has already been created for the eiqIOTC template, so skip to step 3. Otherwise:
   * Select the blue "Create Firmware" button in the top-right of the screen
   * Name your firmware (remember this name for later)
   * Select the eiqIOTC template from the "Template" drop-down (if "eiqIOTC" is not in the list, a firmware for it already exists in your IoTConnect instance)
   * Enter hardware and software version numbers (can be arbitrary such as 0, 0)
   * Select the "Browse" button in the "File" section and select your .zip OTA file
   * Add descriptions if you desire
   * Select the "Save" button
3) Navigate back to the Firmware page and find your new firmware name in the list
4) Under the "Draft" column within the "Software Upgrades" column, click on the draft number (will be "1" for newly-created firmwares)
5) Select the black square with the black arrow under "Actions" to publish your firmware and make it available for OTA

# Launch IoTConnect Program on i.MX 93
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

# View Update on i.MX 93
Shortly after sending the OTA update, you should see an interruption in the telemetry printout on the console of your i.MX 93 informing you that an OTA package was received, downloaded and executed. Additionally, the program is designed to re-start itself after the OTA files have been automatically decompressed and moved to their respective destinations. There is no need for you to do any manual reboots or file manipulation. Your OTA update is complete and the program is already working again!
