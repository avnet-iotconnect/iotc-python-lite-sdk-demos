# SAMA5D27 Basic Demo (For IoTConnect on Azure) 

<img src=".//media/image34.png"/> 

## Step 1: Make an IoTConnect Account
* To get started making an IoTConnect account, you can contact our team at info@iotconnect.io

## Step 2: Sign in to IoTConnect Account
* This demo uses IoTConnect on Azure.
* An IoTConnect account is required to continue with this guide. If you need to create an account, a free 2-month subscription is available. Please follow the [Creating a New IoTConnect Account](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/subscription.md) guide and return to this guide once complete.

## Step 3: Import a Template for Your Device 
* Within this git repo, navigate to the SAMA5D27_Basic_Demo directory and click on the file called basicpoc_template.JSON.

<img src=".//media/image31.png"/>

* Download the template file to your PC by clicking on the download button for the file, shown below.

<img src=".//media/image29.png"/>
  
* On the far-left side of the screen is a navy-blue toolbar, hover your cursor over the icon that looks like a processor chip and choose “Device” out of the dropdown options (shown below). 

<img src=".//media/image1.png"/>

* On the toolbar at the bottom of the page, select the “Templates” tab.

<img src=".//media/image2.png"/>

* On the Templates page, click the “Create Template” button in the top right corner of the screen. 

<img src=".//media/image3.png"/>

* In the upper-right area of the scree, click on the "Import" button.

<img src=".//media/image30.png"/>

* In the resulting pop-up window, click on the "Browse" button, navigate to where you have the template file downloaded, and select the template file. Click on the "Save" button afterwards.

<img src=".//media/image32.png"/>

## Step 4: Create a Your Device in IoTConnect
* Navigate back to the “Device” menu and click on “Create Device” in the top right corner of the screen.

<img src=".//media/image5.png"/>

* For the default configuration, enter the following information:
   * Unique Id: *your unique ID*
   * Display Name: *your display name*
   * Entity: *any entity will work*
   * Template: basicpoc
    
* Change the certificate type to "Auto-Generated" and then click on the yellow/green certificate icon to download your zipped certificated folder.
 
<img src=".//media/image43.png"/>

* Click "Save" at the bottom of the page to finalize the creation of the device.

* Extract the downloaded certificate package folder and save the resulting certificates folder to a known location. You will relocate them later into the setup.

## Step 5: Flash Yocto Image to SD Card
* [Click here](https://www.linux4sam.org/bin/view/Linux4SAM/Sama5d27Som1EKMainPage#eMMC_support_on_SDMMC0) to go to the image download/instructions page for images for the SAMA5D27.
* Download this image:

     <img src=".//media/image36.png"/>

* Follow the "Create a SD card with the demo" section of the instructions to flash the image to an SD card
  * **NOTE: Must be a full-size SD card or a micro-SD card with a full-size adapter since the SAMA5D27 board uses the full-size SD card slot for booting from image**
  * **NOTE: The flashing utility will likely say the flash failed at the very end, but the flash actually completed successfully. It is a non-crtitical verification step that failed. Proceed as normal.**

## Step 6: Prepare Necessary Files
* Download the zipped demo repository [here](https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2Favnet-iotconnect%2Fiotc-python-examples%2Ftree%2Fmain%2FSAMA5D27_Basic_Demo).

* Unzip the downloaded folder, rename it to SAMA5D27_Basic_Demo, and then open it.
  
* Navigate to the *device_certificates* folder.

* Copy your two individual device certificates (device.key and DeviceCertificate.pem) from the folder you saved in Step 4 into this folder. **You cannot copy the whole certificate folder, you must copy the individual files.**

* Back in the *SAMA5D27_Basic_Demo* directory, open up the file *config.py* in a generic text editor.

* To find your CPID and Environment, navigate to your main IoTConnect dashboard page, hover your cursor over the gear icon on the toolbar located on the far-left side of the page, and then click "Key Vault":

<img src=".//media/image9.png"/>

* Your CPID and Environment will be shown as in the image below:

<img src=".//media/image10.png"/>

* Copy your CPID and Environment into the *cpid* and *env* fields of *config.py*, **within the quotation marks.**

* Enter the Unique ID for your device from Step 4 into the *unique_id* field, **within the quotation marks.**

* For this general demo, leave the *plugin* field as "Default"

* Save the *config.py* file and close the text editor.

## Step 7: Connect to the SAMA5D27 over Serial
* Connect your SAMA5D27 to the internet with an ethernet connection to the onboard ethernet port.

* Using the included micro-USB cable, connect the SAMA5D27 board to your computer using the **J10** micro-USB port on the SAMA5D27 and any USB port on your computer.

    <img src=".//media/image39.png"/>

* Check and note which COM port the board is utilizing
  * On Windows computers this can be seen by using the Device Manager
 
     <img src=".//media/image37.png"/>

* Connect to the SAMA5D27 in a terminal emulator using these serial settings (your COM port number may be different):

     <img src=".//media/image38.png"/>

* Insert your SD card into the SD-card port on the board.

* Press the "NRST" button on your SAMA5D27 to reboot the board, causing it to boot from the SD card

  <img src=".//media/image40.png"/>

* After all of the printout from the boot has stopped, the board will ask you to login. Type "root" and hit enter.
  * **NOTE: The "login" prompt may get covered by other prinout after the boot. If you do not see the prompt after the boot has completed (printout has stopped), just type "root" and hit enter anyways. This should get you into the device.**
 
* Execute the command ```ip a``` to get the network connection information for the board. Note the IP address for the eth0 interface because it will be used to transfer the program files to the board.

    <img src=".//media/image41.png"/>

* Transfer your copy of the *SAMA5D27_Basic_Demo* folder with your certificates and updated config to the */home/root* directory of the SAMA5D27 using the "scp" command on a linux computer, or a file transfer tool like [WinSCP](https://winscp.net/eng/index.php) on a Windows computer.

* Back in the terminal emulator serially connected to the SAMA5D27, execute these 3 commands to finalize the setup of the demo on the board (the board will automatically reboot after the script that is run by the last command):
  * ```cd /home/root/SAMA5D27_Basic_Demo```
  * ```chmod +x ./SAMA5D27_Demo_Setup.sh```
  * ```./SAMA5D27_Demo_Setup.sh```
 
* The IoTConnect script has been configured to run as a service automatically after booting, so after the board comes back up the demo will be running and connected to IoTConnect. 

## Step 8: View the Data
* If the "plugin" data field in the config.py file is left as "Default" the main program will send dummy data (random integers) to the "Random_Integer" attribute for the device in IoTConnect.

* Navigate back to the “Device” menu and select your device.
   * You should see that the entry in the "Device Status" column shows a green "CONNECTED" label.

<img src=".//media/image13.png"/>

* Next, in the vertical toolbar on the left side of the page, select "Live Data."

<img src=".//media/image14.png"/>

* Now you can monitor the stream of pseudo-data coming in from the device.

* To send the device commands, navigate to the "Command" tab, select a command from the dropdown menu, and hit "Execute"

<img src=".//media/image42.png"/>

* The 3 different commands don't actually do anything yet for the purposes of this demo, but to verify that the device received the commands, go back to the "Live Data" tab and look for a telemetry message with the "device_messages" attribute included. One should say "IOTCONNECT COMMAND RECEIVED: " followed by the number of the command that you sent. 
