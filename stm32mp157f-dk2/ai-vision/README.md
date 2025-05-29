# X-LINUX-AI Vision Demo: Package Creation and Deployment
This guide will help you upgrade the basic IoTConnect Starter Demo to the X-LINUX-AI Vision Demo with a single update.

>[!IMPORTANT]
> If you have not yet followed the [IoTConnect quickstart guide for this board](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/stm32mp135f-dk/README.md), complete that first and then return here to pick up on Step 1

## 1. Add AIMP1 Template to IoTConnect
Log into your IoTConnect account at [awspoc.iotconnect.io](https://awspoc.iotconnect.io) and navigate to the Device page, and then to the Templates page. Check to see if the **AIMP1** template is present in the list.

If it is not present, download the template by right-clicking [this link](https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/common/templates/AIMP1-template.json) and then clicking "save link as" to save it to your PC.

Back in the online IoTConnect Templates page, click the "Create Template" button in the top-right.

In the resulting page, click "Import" and then browse to find the downloaded template file on your PC. 

After making the selection, click "Save" to finalize the template import. 

## 2. Clone This Git Repository to Your Host Machine
Clone a copy of this repo to your local PC. This is where you will make changes/additions to the demo files.
>[!NOTE]
>On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 3. Customize Package
Inside of the cloned repo (```iotc-python-lite-sdk-demos```), navigate to the ```stm32mp135f-dk/ai-vision/src/``` directory:
```
cd ./stm32mp135f-dk/ai-vision/src
```
By default, this directory contains the necessary files to upgrade from the basic quickstart application to the AI Vision demo.

## 4. Create Package
Navigate back to the ```ai-vision``` directory and then run this command to create ```package.tar.gz``` which includes the necessary demo files and installation script:
```
bash ./create-package.sh
```
>[!NOTE]
> At the end of the package creation script, ```package.tar.gz``` is automatically copied into the ```common``` directory so it can be readily accessed by the scripts used in optional steps 7B and 7C.

## 5. Physically Set Up Demo Equipment
* Using a stand, adhesive, zip-ties, or some other type of binding utility, secure your USB camera in a position to be looking at your designated detection area.

>[!TIP]
>To maintain a consistent and controlled background, it is recommended to position the camera above a tabletop secured to a boom arm (such as [this](https://www.amazon.com/dp/B0BV2SBWVD?ref=cm_sw_r_apan_dp_XVFHFPZQA55SFZY5S988&ref_=cm_sw_r_apan_dp_XVFHFPZQA55SFZY5S988&social_share=cm_sw_r_apan_dp_XVFHFPZQA55SFZY5S988&peakEvent=1&starsLeft=1&skipTwisterOG=1&th=1)), looking down at objects on the table.

>[!IMPORTANT]
>The AI Vision Demo requires a USB UVC-Compliant Camera (such as [this](https://www.amazon.com/ALPCAM-Distortion-Compliant-Embedded-Industrial/dp/B0B1WTV1KB/ref=sr_1_40?crid=1Y64R6N37I2DW&dib=eyJ2IjoiMSJ9.09vlNQuRgZXBCOJltq5NAHjwkF3xrkD_IO8iIPnTgmM656JhZdERupdaYL29K-WbqLGgdkCchkhjMGFCFpy7D4Ng5LfWuSsYX1jMf8HFDXXsuqE96PFQrpwZszNnYEAkgDOKVRYky4lgiGU4S8NZZEcnmANwxdgvAOnkQCDQWIYxf2Tau45lZyN0ZjY5Otk6.TwrVuCH8OFqthDivTQqbOEPSUYAmvtH5LiE27DyAm7A&dib_tag=se&keywords=usb%2Bcamera%2Buvc&qid=1732315805&sprefix=usb%2Bcamera%2Buvc%2Caps%2C148&sr=8-40&th=1)). Using a non-UVC camera (most modern webcams, for example) will cause the vision program to crash due to image format incompatibilities.

>[!NOTE]
> The detection program works best with good lighting and non-glossy objects against a non-glossy background with good color-contrast versus the colors of the objects being detected. Ideally the objects are between 6 and 24 inches away from the camera lens (depends on size of object). 

* Plug your USB camera into a USB port on the STM32MP135F-DK
 
## 6. Prepare Device to Receive Package
The most basic way to deliver and run the install package is through a local file transfer. See step 5A below for instructions on this method.

For your board to receive the package through IoTConnect, it must be actively connected. Do this by running the main IoTConnect program on your board called ```app.py```:

From here, you have the option to push the package to your devices directly to your device in one of the following ways:
* From you host machine's console as an OTA (see step 7B)
* Through an API device command (see step 7C)
* Through the online IoTConnect platform as an OTA (see step 7D)

## 7A. Deliver Package Through Local File Transfer
To deliver your package to a device through a local file transfer, the recommended method is to use an ```scp``` (secure copy) command. 

First find the active IP address of your device and then use that IP address to copy ```package.tar.gz``` into the main application directory of the device (```/home/weston/demo```).  

After the file transfer is complete, open a terminal on your device, naviagte to the main application directory, and verify that there is a ```package.tar.gz``` present.

If ```package.tar.gz``` is there, run this command to decompress the file and overwrite existing files in the directory:

```
tar -xzf package.tar.gz --overwrite
```
Navigate to your device in the "Device" page of IoTConnect in your browser and locate the "Template" selection (mid-left on the page)

Click the "pen and paper" icon next to the template name to open a dropdown where you select a new template.

Select the "AIMP1" template.

Lastly, back in your device terminal, execute the ```install.sh``` script to perform any additional file movements/modifications that you programmed into your install package:
```
bash ./install.sh
```

## 7B. Push Package via OTA From Host Machine Console
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

Navigate into the ```/common/scripts/``` directory of you cloned repo and run this command:
```
python3 ota-package-send.py
```
You will be prompted to enter the unique IDs of the devices you wish to send the OTA package to. You will also be asked if you need to change the template for your device. Enter "Y" and then enter "AIMP1" for the new template name. If AIMP1 does not yet have an associated firmware, you will also be prompted for a name for the new firmware to be created (can be whatever you want).

The ```package.tar.gz``` file you generated previously will be automatically uploaded to an upgrade for the new/existing firmware, and the OTA package will be automatically pushed.

You should then see this output in your host machine console:
```
Successful OTA push!
```

## 7C. Push Package Through Command From Host Machine Console
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

Navigate into the ```/common/scripts/``` directory of you cloned repo and run this command:
```
python3 cmd-package-send.py
```
You will be prompted to enter the unique IDs of the devices you wish to send the package to. All of the devices must use the same template. Any devices that use a template different from the first device entered will be rejected. 

After entering your device IDs, the ```package.tar.gz``` file you generated previously will be automatically uploaded and the command will be automatically pushed to all given devices.

For every device that receives the command, you should see this ouput in your host machine console:
```
Command successful!
```

After the command is sent to all given devices, you will see a tally of successful and failed commands in your host machine console as well.


## 7D. Upload and Push Package Through OTA in IoTConnect Online Platform
1) In the "Device" Page of the online IoTConnect platform, on the blue toolbar at the bottom of the page select "Firmware"
2) If a firmware has already been created for your device's template, skip to step 3. Otherwise:
   * Select the blue "Create Firmware" button in the top-right of the screen
   * Name your firmware (remember this name for later)
   * Select your device's template from the "Template" drop-down (if your device's template is not in the list, a firmware for it already exists in your IoTConnect instance)
   * Enter hardware and software version numbers (can be arbitrary such as 0, 0)
   * Select the "Browse" button in the "File" section and select your ```package.tar.gz```
   * Add descriptions if you desire
   * Select the "Save" button
3) Navigate back to the Firmware page and find your new firmware name in the list
4) Under the "Draft" column within the "Software Upgrades" column, click on the draft number (will be "1" for newly-created firmwares)
5) Select the black square with the black arrow under "Actions" to publish your firmware and make it available for OTA
6) Navigate to your device back in the "Device" page and locate the "Template" selection (mid-left on the page)
7) Click the "pen and paper" icon next to the template name to open a dropdown where you select a new template.
8) Select the "AIMP1" template.
9) Back in the "Firmware" page of IoTConnect, select the "OTA Updates" button in the top-right of the screen
10) For "Hardware Version" select your firmware's name with the hyphenated hardware version from the drop-down
11) Select the software version you chose for your firmware
12) For "Target" select "Devices" from the drop-down
13) Select your device's unique ID from the "Devices" drop-down
14) Click the blue "Update" button to initialize the OTA update

## 8. View Update in Device Console
Shortly after sending the update via any method, you should see an interruption in the telemetry printout on the console of your device informing you that an update package was received, downloaded and executed. 

The program is designed to re-start itself after the update files have been automatically decompressed and the ```install.sh``` script is executed (if included). There is no need for you to do any manual reboots or file manipulation. Your package installation is complete and the program is working again already!

## 9. Monitor Object Detection Data in IoTConnect
* Approximately once per second while the demo program is active, a data packet will be sent to IoTConnect containing this information:
   * Attribute Name: objects_detected
     * Attribute Type: string
     * Attribute Description: A string containing comma-separated label names of all objects currently detected, including their confidence percentages in parentheses. String is ordered from highest percentage confidence to lowest percentage.
   * Attribute Name: detection_data
     * Attribute Type: object
     * Attribute Description: An object that breaks down the detected object information into individual string and decimal values to be used in more robust dashboards.

* To view the live data, go to your device in IoTConnect, verify it is connected, and click on the "Live Data" tab.

* The vision program is trained to recognize any object in [this list](object-labels.txt) but from our experimentation, some of the most consistently-detected and conveniently-sized objects to use are:
```
apple
orange
banana
donut
remote
scissors
cell phone
```
>[!NOTE]
>Instead of the physical objects, printing out decent-quality images of the objects onto paper (not glossy photograph paper) and putting those in front of the camera can result in detections of objects that typically would not be feasible for the demo (such as airplane, stop sign, giraffe, etc.). There have been mixed results with this, usually dependent on how life-like the images are.

>[!TIP]
>Adjusting the lighting, distance from the camera, background, and confidence threshold can help with more-consistent detection
