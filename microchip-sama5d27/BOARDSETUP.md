# Microchip SAMA5D27 Board Setup 

<img src=".//media/sama5d27-product.png"/> 

## Step 1: Flash Yocto Image to SD Card
* [Click here](https://www.linux4sam.org/bin/view/Linux4SAM/Sama5d27Som1EKMainPage#eMMC_support_on_SDMMC0) to go to the image download/instructions page for images for the SAMA5D27.
* Download this image:

     <img src=".//media/image-download.png"/>

* Follow the "Create a SD card with the demo" section of the instructions to flash the image to an SD card
>[!IMPORTANT]
>Must be a full-size SD card or a micro-SD card with a full-size adapter since the SAMA5D27 board uses the full-size SD card slot for booting from image.

>[!NOTE]
> The flashing utility will likely say the flash failed at the very end, but the flash actually completed successfully. It is a non-crtitical verification step that failed. Proceed as normal.

## Step 2: Connect to the SAMA5D27 over Serial
* Connect your SAMA5D27 to the internet with an ethernet connection to the onboard ethernet port.

* Using the included micro-USB cable, connect the SAMA5D27 board to your computer using the **J10** micro-USB port on the SAMA5D27 and any USB port on your computer.
  
    <img src=".//media/j10-diagram.png"/>

>[!NOTE]
>This USB connection also serves as the power supply to the board.

* Check and note which COM port the board is utilizing
  * On Windows computers this can be seen by using the Device Manager
 
     <img src=".//media/device-manager.png"/>

* Connect to the SAMA5D27 in a terminal emulator using these serial settings (your COM port number may be different):

     <img src=".//media/putty.png"/>

* Insert your SD card into the SD-card port on the board.

* Press the "NRST" button on your SAMA5D27 to reboot the board, causing it to boot from the SD card

  <img src=".//media/reset-diagram.png"/>

* After all of the printout from the boot has stopped, the board will ask you to login. Type "root" and hit enter.
>[!NOTE]
> The "login" prompt may get covered by other prinout after the boot. If you do not see the prompt after the boot has completed (printout has stopped), just type "root" and hit enter anyways. This should get you into the device.

 ## Step 3: Set Up and Run the Python Lite SDK Demo
* Execute the command ```apt-get update``` to check for and install updates for the system

* For the rest of the demo setup and execution processes, follow the instructions in the [Python Lite SDK Quickstart Guide](https://github.com/avnet-iotconnect/iotc-python-lite-sdk/blob/main/QUICKSTART.md)
