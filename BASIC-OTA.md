# Creating and Deploying an Update for IoTConnect Python Lite Demos

## Introduction
This document will help you create and deploy an update package for any IoTConnect Python Lite SDK Demo.

An update package can do any/all of the following:
* Update existing demo files
* Update certificates
* Add new files to a demo (such as new AI models)
* Re-install the IoTConnect Python Lite SDK with the newest available version.

## 1. Clone This Git Repository to Your Host Machine
Clone a copy of this repo to your local PC. This is where you will make changes/additions to the demo files.
>[!NOTE]
>On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 2. Modify and Add Files
After navigating into the "core-files" directory, modify any of the the files as desired. 

You can add additional files to your demo (such as AI models or replacement certificates) by adding them to the "additional-files" directory.

Inside of the "ota" directory is a bare-bones version of the install.sh script. This script gets automatically run on the target device when the update package is received and extracted. 
By default the script is only comments (no actions are necessary for the default demo), but if you want the update to automatically re-install the IoTConnect Python Lite SDK with the newest available version, open install.sh inside of a text editor and find this section of the script:

```
# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
# python3 -m pip install --force-reinstall iotconnect-sdk-lite
# ---------------------------------------------------------------------
```
Since it is commented out, the script **will not** re-install the SDK. To enable the re-install, simply backspace the "# " (remove the trailing space as well to align the command) and then save the file.

A modified version that **will** re-install the SDK will look like this:
```
# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
python3 -m pip install --force-reinstall iotconnect-sdk-lite
# ---------------------------------------------------------------------
```

If your update package includes additional files that need to go in specific directories (not in the same directory as the main IoTConnect program), you will need to make further modifications to install.sh to include commands to move the files to their desired directories.

For example, adding this code to the end of install.sh will move any TFLITE model files from the current directory (where the .tar.gz file was extracted and where the main IoTConnect program is) into the "/usr/bin/eiq-examples-git/models" directory:
```
# Define the target directories
target_dir_tflite="/usr/bin/eiq-examples-git/models"

# Loop through each file in the current directory
for file in *; do
  # Check if it's a file (not a directory)
  if [ -f "$file" ]; then
    case "$file" in
      *.tflite)
        # Move .tflite files to /usr/bin/eiq-examples-git/models
        mv "$file" "$target_dir_tflite"
        echo "Moved $file to $target_dir_tflite"
        ;;
      *)
        # If the file doesn't match any condition, do nothing
        ;;
    esac
  fi
done
```
>[!NOTE]
>For the IoTConnect Python Lite SDK, device certificates are stored in the same directory as the main IoTConnect program. Therefore, they do not need to be moved at all upon extraction. They will automatically overwrite the existing certificates.

## 3. Create Update Package
Within the "update-files" directory, run this command:
```
bash ./generate-payload.sh
```
You now have a payload file called "update-payload.tar.gz"

## 4. Launch IoTConnect Program on Device
For your board to receive the update, it must be actively connected to IoTConnect. Do this by running the main IoTConnect program on your board called "app.py":

```
cd /home/weston/demo
python3 app.py
```

From here, you have the option to push the update to your devices directly from you host machine's console as an OTA update (see step 5A), through an API device command (see step 5B), or you can upload the payload to the online IoTConnect platform and push an OTA update from there (see step 5C).

## 5A. Push OTA Update From Host Machine Console
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

Navigate into the "update-files" directory of you cloned repo (same place as "core-files" and "additional-files") and run this command:
```
python3 ota-update.py
```
You will be prompted to enter the unique IDs of the devices you wish to send the OTA update to. If the firmware for your listed devices does not yet have an associated firmware, you will also be prompted for a name for the new firmware to be created.

The "update-payload.tar.gz" file you generated previously will be automatically uploaded to an upgrade for the new/existing firmware, and the OTA update will be automatically pushed.

You should then see this output in your host machine console:
```
Successful OTA push!
```


## 5B. Push Update as Command From Host Machine Console
Pushing an update from your local machine requires you to be logged into your IoTConnect account so it can utilize the IoTConnect REST API.

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

Navigate into the "update-files" directory of you cloned repo (same place as "core-files" and "additional-files") and run this command:
```
python3 cmd-update.py
```
You will be prompted to enter the unique IDs of the devices you wish to send the update to. All of the devices must use the same template. Any devices that use a template different from the first device entered will be rejected. 

After entering your device IDs, the "update-payload.tar.gz" file you generated previously will be automatically uploaded and the command will be automatically pushed to all given devices.

For every device that receives the command, you should see this ouput in your host machine console:
```
Update command successful!
```

After the command is sent to all given devices, you will see a tally of successful and failed commands in your host machine console as well.


## 5C. Upload/Push OTA Update in IoTConnect Online Platform
1) In the "Device" Page of the online IoTConnect platform, on the blue toolbar at the bottom of the page select "Firmware"
2) If a firmware has already been created for your device's template, skip to step 3. Otherwise:
   * Select the blue "Create Firmware" button in the top-right of the screen
   * Name your firmware (remember this name for later)
   * Select your device's template from the "Template" drop-down (if your device's template is not in the list, a firmware for it already exists in your IoTConnect instance)
   * Enter hardware and software version numbers (can be arbitrary such as 0, 0)
   * Select the "Browse" button in the "File" section and select your ```update-payload.tar.gz```
   * Add descriptions if you desire
   * Select the "Save" button
3) Navigate back to the Firmware page and find your new firmware name in the list
4) Under the "Draft" column within the "Software Upgrades" column, click on the draft number (will be "1" for newly-created firmwares)
5) Select the black square with the black arrow under "Actions" to publish your firmware and make it available for OTA
6) In the "Firmware" page of IoTConnect, select the "OTA Updates" button in the top-right of the screen
7) For "Hardware Version" select your firmware's name with the hyphenated hardware version from the drop-down
8) Select the software version you chose for your firmware
9) For "Target" select "Devices" from the drop-down
10) Select your device's unique ID from the "Devices" drop-down
11) Click the blue "Update" button to initialize the OTA update

## 6. View Update in Device Console
Shortly after sending the update via any method, you should see an interruption in the telemetry printout on the console of your device informing you that an update package was received, downloaded and executed. 

Additionally, the program is designed to re-start itself after the update files have been automatically decompressed and moved to their respective destinations via the "install.sh" script included in the package. There is no need for you to do any manual reboots or file manipulation. Your update is complete and the program is already working again!
