# Flashing a Fresh Default Image onto an NXP i.MX 93 Development Board

# 1. Introduction
This simple guide will help you download all the necessary files for flashing a fresh stock image to an NXP i.MX 93, and then flash the image to the board.

>[!NOTE]
>This guide is to be used with a Windows host machine. If you are using a Linux machine, the actual flashing utility step is likely similar but will not be exactly the same.

# 2. Download Universal Update Utility (UUU)
* Download the executable of the latest release of the Universal Update Utility (UUU) by clicking [this link](https://github.com/nxp-imx/mfgtools/releases/download/uuu_1.5.201/uuu.exe)

# 3. Download Image Files
* Go to NXP's [FRDM-IMX93 Product Page](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDM-IMX93)
* Click on the "Design Resources" tab and then scroll down to the "Software" section
* Click the "Download" button next to "FRDM-IMX93 Demo Images"
* Accept the Software License Agreement and the download should automatically start

# 4. Organize Files for Flashing
* Unzip the zipped image folder you downloaded
* Copy the uuu.exe file you previously downloaded into the newly-unzipped image folder

# 5. Prepare Hardware for Flashing
* Set the boot dip-switches (SW1) to OFF-OFF-OFF-ON for Serial Download mode
* Connect a USB-C cable from your host machine to the USB1_C port (located next to the audio jack) on the i.MX 93
>[!IMPORTANT]
>Connecting to the POWER or DEBUG USB-C ports on the board **will not** work. You must connect to the USB1_C port.
* Power the board with a second USB-C cable connected to the POWER port

# 6. Flash the Image
* Open a Windows Powershell window
* Move into the unzipped downloaded image folder conatining the image files and uuu.exe
* Execute this command to start the flash:
  ```.\uuu.exe -b emmc_all .\imx-boot-imx93-11x11-lpddr4x-evk-sd.bin-flash_singleboot .\imx-image-full-imx93evk.wic```
* Wait until the flash is complete
* Change the boot dip-switches (SW1) back to OFF-OFF-ON-OFF for eMMC boot mode
* Reboot the board by unplugging the power cable and plugging it back in
* Your i.MX 93 now has booted with a fresh default image on it
