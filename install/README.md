# Creating and Deploying an Install Package for IoTConnect Python Lite Demos

>[!IMPORTANT]
>Make sure you have completed the Quickstart Guide for your specific board before pushing any installation or update packages. There are basic, mandatory IoTConnect functionalities that are set up in the Quickstart process such as device onboarding and certificate creation. To find a device's Quickstart Guide, navigate back to the top directory of this repository and then navigate to the directory named after your specific device. The README within that directory will be the Quickstart Guide.

## Introduction
This document will help you create and deploy an install package for any IoTConnect Python Lite SDK Demo.

The package can do any/all of the following:
* Add new files to a device
* Install new modules/libraries on a device
* Update existing demo files
* Update certificates
* Re-install the IoTConnect Python Lite SDK with the newest available version.

## 1. Clone This Git Repository to Your Host Machine
Clone a copy of this repo to your local PC. This is where you will make changes/additions to the demo files.
>[!NOTE]
>On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 2. Modify and Add Files
After navigating into the ```/install/package/``` directory, modify ```app.py``` as desired. 

You can add additional files to your demo (such as AI models or replacement certificates) by adding them to the ```/install/package/``` directory.

Inside of the ```/install/package/``` directory is a bare-bones version of the ```install.sh``` script. This script gets automatically run on the target device when the package is received and extracted. 
By default the script is only comments (no actions are necessary for the default demo), but if you want the update to automatically re-install the IoTConnect Python Lite SDK with the newest available version, open install.sh inside of a text editor and find this section of the script:

```
# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
# python3 -m pip install --force-reinstall iotconnect-sdk-lite
# ---------------------------------------------------------------------
```
Since it is commented out, the script **will not** re-install the SDK. To enable the re-install, simply backspace the ```# ``` (remove the trailing space as well to align the command) and then save the file.

A modified version that **will** re-install the SDK will look like this:
```
# ---------UN-COMMENT THIS COMMAND TO ENABLE SDK RE-INSTALLATION-------
python3 -m pip install --force-reinstall iotconnect-sdk-lite
# ---------------------------------------------------------------------
```

If your package includes additional files that need to go in specific directories (not in the same directory as the main IoTConnect program), you will need to make further modifications to ```install.sh``` to include commands to move the files to their desired directories.

For example, adding this code to the end of ```install.sh``` will move any TFLITE model files from the current directory (where the .tar.gz file was extracted and where the main IoTConnect program is) into the ```/usr/bin/eiq-examples-git/models``` directory:
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

## 3. Create Package
Within the ```/install/scripts/``` directory, run this command:
```
bash ./generate-payload.sh
```
You now have a file called ```install-package.tar.gz``` in the ```/install/package/``` directory.

## 4. Prepare Device to Receive Package
The most basic way to deliver and run the install package is through a local file transfer. Usually this method would be used on a new board that does not yet have any IoTConnect program on it. See step 5A below for instructions on this method.

For your board to receive the package through IoTConnect, it must be actively connected. Do this by running the main IoTConnect program on your board called ```app.py```:

From here, you have the option to push the package to your devices directly to your device in one of the following ways:
* From you host machine's console as an OTA (see step 5B)
* Through an API device command (see step 5C)
* Through the online IoTConnect platform as an OTA (see step 5D)

## 5A. Deliver Package Through Local File Transfer
To deliver your package to a device through a local file transfer, the recommended method is to use an ```scp``` (secure copy) command. 

First find the active IP address of your device and then use that IP address to copy ```install-package.tar.gz``` into the main application directory of the device. The main application directory for each supported device is noted in the specific device's directory's README within this repository (usually ```/home/weston/demo``` for Yocto-based devices).  

After the file transfer is complete, open a terminal on your device, naviagte to the main application directory, and verify that there is a ```install-package.tar.gz``` present.

If ```install-package.tar.gz``` is there, run this command to decompress the file and overwrite existing files in the directory:

```
tar -xzf install-package.tar.gz --overwrite
```
Lastly, execute the ```install.sh``` script to perform any additional file movements/modifications that you programmed into your install package:
```
bash ./install.sh
```

## 5B. Push Package via OTA From Host Machine Console
Pushing an OTA from your local machine requires you to be logged into your IoTConnect account so it can utilize the IoTConnect REST API.

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

Navigate into the ```/install/scripts/``` directory of you cloned repo and run this command:
```
python3 ota-package-send.py
```
You will be prompted to enter the unique IDs of the devices you wish to send the OTA package to. If the firmware for your listed devices does not yet have an associated firmware, you will also be prompted for a name for the new firmware to be created.

The ```install-package.tar.gz``` file you generated previously will be automatically uploaded to an upgrade for the new/existing firmware, and the OTA package will be automatically pushed.

You should then see this output in your host machine console:
```
Successful OTA push!
```


## 5C. Push Package Through Command From Host Machine Console
Pushing an package from your local machine requires you to be logged into your IoTConnect account so it can utilize the IoTConnect REST API.

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

Navigate into the ```/install/scripts/``` directory of you cloned repo and run this command:
```
python3 cmd-package-send.py
```
You will be prompted to enter the unique IDs of the devices you wish to send the package to. All of the devices must use the same template. Any devices that use a template different from the first device entered will be rejected. 

After entering your device IDs, the ```install-package.tar.gz``` file you generated previously will be automatically uploaded and the command will be automatically pushed to all given devices.

For every device that receives the command, you should see this ouput in your host machine console:
```
Command successful!
```

After the command is sent to all given devices, you will see a tally of successful and failed commands in your host machine console as well.


## 5D. Upload and Push Package Through OTA in IoTConnect Online Platform
1) In the "Device" Page of the online IoTConnect platform, on the blue toolbar at the bottom of the page select "Firmware"
2) If a firmware has already been created for your device's template, skip to step 3. Otherwise:
   * Select the blue "Create Firmware" button in the top-right of the screen
   * Name your firmware (remember this name for later)
   * Select your device's template from the "Template" drop-down (if your device's template is not in the list, a firmware for it already exists in your IoTConnect instance)
   * Enter hardware and software version numbers (can be arbitrary such as 0, 0)
   * Select the "Browse" button in the "File" section and select your ```install-package.tar.gz```
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


## 6. View Package Reception in Device Console
Shortly after sending the package via any method other than a local file transfer, you should see an interruption in the telemetry printout on the console of your device informing you that a package was received, downloaded and executed. 

Additionally, the program is designed to re-start itself after the package files have been automatically decompressed and moved to their respective destinations via the ```install.sh``` script included in the package. There is no need for you to do any manual reboots or file manipulation. Your install package delivery is complete and the program is already working again!
