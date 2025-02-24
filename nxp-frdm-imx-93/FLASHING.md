# Flashing the Default Image onto an NXP i.MX 93 Development Board

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
* Copy the uuu.exe file you previously downloaded into the of the newly-unzipped image folder (you may need to navigate an additional layer into the folder after unzipping it to get to where the real files are)
* Using 7-Zip (or another unzipping utility that supports ZST files), unzip this file (keeping the same destination directory):
  ```imx-image-full-imx93frdm.rootfs.wic.zst```
* Before proceeding to the next step, very that these 3 files are all within the same folder:  
```imx-image-full-imx93frdm.rootfs.wic```  
```imx-boot-imx93frdm-sd.bin-flash_singleboot```  
```uuu.exe```  

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
  ```
  .\uuu.exe -b emmc_all .\imx-image-full-imx93frdm.rootfs.wic
  ```
* Wait until the flash is complete (should take ~5 minutes)
* Change the boot dip-switches (SW1) back to OFF-OFF-ON-OFF for eMMC boot mode
* Reboot the board by unplugging the power cable and plugging it back in
* Your i.MX 93 now has booted with a fresh default image on it
