# STM32MP157F-DK2 Demos (For IoTConnect on AWS)

The demos in this directory use a [Discovery kit with STM32MP157F MPU](https://www.st.com/en/evaluation-tools/stm32mp157f-dk2.html) to run an IoTConnect program to monitor precise telemetry data in real-time on the IoTConnect cloud platform using AWS. 

<img src=".//media/image34.png"/> 

## Step 1: Make an IoTConnect Account
* To get started making an IoTConnect account, you can contact our team at info@iotconnect.io

## Step 2: Sign in to IoTConnect Account
* This demo uses IoTConnect on AWS.
* An IoTConnect account is required to continue with this guide. If you need to create an account, a free 2-month subscription is available. Please follow the [Creating a New IoTConnect Account](https://github.com/avnet-iotconnect/avnet-iotconnect.github.io/blob/main/documentation/iotconnect/subscription/subscription.md) guide and return to this guide once complete.

## Step 3: Import a Template for Your Device 
* Within this git repo, navigate to the PROTEUS_MP157F_Demo directory and click on the file called MP157F_template.JSON.

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

* For the default configuration (no device naming configuration in final script), enter the following information and then click “Save and View”:
   * Unique Id: STM32MP157F
   * Display Name: STM32MP157F
   * Entity: (Any Generic Entity Will Work)
   * Template: MP157F
     
* For a custom UniqueID/DisplayName (device naming configuration in final script), enter the following information and then click “Save and View”:
   * Unique Id: <Your UniqueID/DisplayName Here>
   * Display Name: <Your UniqueID/DisplayName Here>
   * Entity: (Any Generic Entity Will Work)
   * Template: MP157F
 
      * **NOTE: For setup simplicity, this demo is deisgned for the Unique ID and the Display Name to be exactly the same, so it is critical that you make them identical to each other. It will not work otherwise.**
 
<img src=".//media/image6.png"/>

* In the resulting page, click “Connection Info” in the top-right corner of the page.

<img src=".//media/image7.png"/>

* Click on the yellow and green certificate icon in the top-right corner of the resulting pop-up to download the zipped certificate package.

<img src=".//media/image8.png"/>

* Extract the certificate package folder and save the resulting certificates folder to a known location. You will relocate them later into the setup.

## Step 6: Flash IoTConnect-Compatible Image to STM32MP157F-DK2 Board
* To download the zipped image folder, [click here](https://saleshosted.z13.web.core.windows.net/sdk/st/stmp1/proteus/OSTL_6.1_IoTConnect_Compatible.zip).
* Unzip the folder to a known location.
* Download and Install the [STM32CubeProgrammer](https://www.st.com/en/development-tools/stm32cubeprog.html) software (the utility for flashing the image to the device).
   * You may have to create an ST account (it's free) to get access to the software download.
* Set up the STM32MP157F-DK board for flashing:
   * On the underside of the board, flip both of the large dipswitches (directly opposite of the HDMI port) to the "OFF" position.
  
      <img src=".//media/image16.png"/>
      
   * Power the board with a USB-C cable connected to the "PWR_IN" USB-C port connected to a 5VDC supply with at least 1.0A of output.
   
      <img src=".//media/image19.png"/>
      
   * Connect the USB-C "USB" port of your board to your PC with the included USB-C cable.
      * If your PC does not have a USB-C port, you may use a USB-A to USB-C cable and connect it to a normal USB-A port on your PC.
   
      <img src=".//media/image20.png"/>
   
   * Insert the included SD card into the SD card slot on the board.
      
   * Push the "RESET" button on your board to ensure it boots into flashing mode (the LCD display of the board should be black when it has booted into flashing mode).

<img src=".//media/image18.png"/>
      
* Run the STM32CubeProgrammer software and click on the "Open file" tab.

<img src=".//media/image21.png"/>
      
* Navigate to the directory where you have the unzipped "OpenSTLinux_IoTConnect_Compatible" folder, and then navigate through the folder to get to this directory: {Your preliminary directory}\OSTL_6.1_IoTConnect_Compatible\images\stm32mp1\flashlayout_st-image-weston\optee
   * Select the FlashLayout_sdcard_stm32mp157F-dk2-optee.tsv file and then click "Open." 
   
<img src=".//media/image22.png"/>
      
* Next, click on the "Browse" button to select the binaries path.
   
<img src=".//media/image23.png"/>
   
* Navigate once again to the directory where you have the unzipped "OpenSTLinux_IoTConnect_Compatible" folder, and then navigate through the folder to get to this directory: {Your preliminary directory}\OSTL_6.1_IoTConnect_Compatible\images\stm32mp1
   * Select the stm32mp1 folder and then click "Select folder."

<img src=".//media/image24.png"/>
      
* Back in the STM32CubeProgrammer window, on the right-hand side of the screen, if the "Port" is listed as "No DFU...," make sure your USB cable is connected both to your PC and the board, and then click the revolving arrows icon.

<img src=".//media/image25.png"/>
     
* When the device is recognized by the software, the port listing will be "USB" followed by a number, such as 1. The serial number of your board should also be listed beneath the port name.

<img src=".//media/image26.png"/>
    
* You are ready to flash. Click the "Download" button to begin the flashing process.
   * The STM32MP157F-DK2 will turn off and on several times throughout the flashing process. It is important to not unplug or disturb it during the process. Given the size of the image it will usually take **up to 45 minutes** to flash.
   * It is worth noting that the LCD screen on the board will turn on with some output text during the flash process, so do not be alarmed.

<img src=".//media/image27.png"/>
   
* When the flash has completed successfully, this pop-up in the STM32CubeProgrammer window will appear.

<img src=".//media/image28.png"/>
   
* Now, flip the large dipswitches on the underside of your board both to the "ON" position, and once again hit the reset button to properly boot the new image from the SD card.

<img src=".//media/image17.png"/>
   
* **For the first boot after flashing, the board takes a few minutes to turn on.**

* To complete the setup process:
   * Connect your board to the internet by either using an ethernet cable, or by following the optional Wi-Fi configuration step below.
   * You will also need to connect the STM32MP157 Discovery kit to your PC using a USB-A to micro-USB cable. Connect to the assigned COM Port using serial console application, such as [Tera Term](https://ttssh2.osdn.jp/index.html.en), or a browser application like [Google Chrome Labs Serial Terminal](https://googlechromelabs.github.io/serial-terminal/). Optionally, you may connect the board to an external monitor using the HMDI port and a keyboard/mouse.
      

## Step 7: Prepare Necessary Files
* In another browser tab, navigate to [the top of this repository] (https://github.com/avnet-iotconnect/iotc-python-examples/tree/main) and download the repository's zip file as shown here:

<img src=".//media/image_a.png"/>

* Unzip the downloaded folder and then open it.
  
* Navigate to the *iotc-python-examples-main* directory (the name of the overall repo and the first sub-directory will have the same name)
  
* Copy the *STM32MP157F_Demo* folder to a flash drive. This is the only part of the repository you will need for this demo.

* In the *STM32MP157F_Demo* directory on your flash drive, navigate to the *device_certificates* folder.

* Copy your two individual device certificates from the folder you saved in Step 4 into this folder. **You cannot copy the whole certificate folder, you must copy the individual *.pem* and *.crt* files.**

* Back in the *STM32MP157F_Demo* directory, open up the file *config.py* in a generic text editor.

* To find your CPID and Environment, navigate to your main IoTConnect dashboard page, hover your curson over the gear icon on the tollbar located on the far-left side of the page, and then click "Key Vault":

<img src=".//media/image9.png"/>

* Your CPID and Environment will be shown as in the image below:

<img src=".//media/image10.png"/>

* Copy your CPID and Environment into the *cpid* and *env* fields of *config.py*, **within the quotation marks.**

* Enter the Unique ID for your device from Step 4 into the *unique_id* field, **within the quotation marks.**

* For this general demo, leave the *plugin* field as "Default"
  *  To connect your gateway to a sensor and acquire real data, refer to the appropriate README for the supported sensor pack within the [plugins](https://github.com/avnet-iotconnect/iotc-python-examples/tree/main/STM32MP157F-DK2_Demo/plugins) directory.

* Save the *config.py* file and close the text editor.

* Now remove the flash drive from your PC and insert it into a USB port on the STM32MP157F-DK2 gateway.

## Step 8: Configure the Gateway

* These steps can be completed using the serial terminal connected to the ST Discovery board, or using the weston terminal directly on the gateway.

* First, get admin privileges by entering this command:
  * ```su```

* Create a directory for the flash drive to mount to with this command:
  * ```mkdir /media/usbdrive```

* Now, mount the flash drive using this command:
  * ```mount /dev/sda1 /media/usbdrive```
    * If that command fails (will only fail if you have plugged/unplugged the flash drive from the gateway more than once), use this longer command instead:
      * ```mount /dev/sdb1 /media/usbdrive || mount /dev/sdc1 /media/usbdrive || mount /dev/sdd1 /media/usbdrive```

* **Wi-Fi Configuration (OPTIONAL)**
  * To connect the gateway to the wireless network, execute this command:
    * ```/media/usbdrive/PROTEUS_MP157F_Demo/Wifi_Setup.sh```
      * NOTE: You will be asked to enter your network SSID and password during this script, as well as if it is your first time connecting the gateway to Wi-Fi
        * If you have already connected the gateway to Wi-Fi before and need to change the SSID or password, simply run the script again and answer **Y** to the first prompt
 
* Execute this command to run the rest of the automatic gateway setup:
  * ```/media/usbdrive/PROTEUS_MP157F_Demo/Proteus_Demo_Setup.sh```
  * **NOTE: This setup script will take several minutes to complete.** 
 
* The main IoTConnect program has been configured to run on boot, so now reboot the gateway with the command:
  * ```reboot```

## Step 9: View the Data
* If the "plugin" data field in the config.py file is left as "Default" the main program will send dummy data (random integers) to the "Random_Integer" attribute for the device in IoTConnect.

  * To connect your gateway to a sensor and acquire real data, refer to the appropriate README for the supported sensor pack within the [plugins](https://github.com/avnet-iotconnect/iotc-python-examples/tree/main/STM32MP157F-DK2_Demo/plugins) directory.

* Navigate back to the “Device” menu and select your device named "STM32MP157F" (or your custom Display Name if you did not use the default).
   * You should see that the entry in the "Device Status" column shows a green "CONNECTED" label.

<img src=".//media/image13.png"/>

* Next, in the vertical toolbar on the left side of the page, select "Live Data."

<img src=".//media/image14.png"/>

* To get a more human-friendly report of the live telemetry data, click on the "Tabular" tab.
   * This tab allows you to scroll vertically to view previous data entires, and horizontally to see each individual attribute.

<img src=".//media/image15.png"/>
