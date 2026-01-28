# MKBOXPRO Demo: Package Creation and Deployment

This guide will help you upgrade the basic /IOTCONNECT Starter Demo on the STM32MP135F-DK to the MKBOXPRO sensor pack
demo with a single package.

> [!IMPORTANT]
> The installation of this demo depends on a pre-compiled .whl file for a key BLE package that is made specifically for
> Python 3.12, so it will only work on the **Scarthgap** Yocto release. Make sure your STM32MP135F-DK is loaded with a
> Scarthgap image before proceeding through any other steps.

> [!NOTE]
> Make sure your MKBOXPRO sensor pack is loaded with the correct firmware by
> following [this MKBOXPRO setup guide](MKBOXPRO-SETUP.md) before attempting to run this demo.

> [!IMPORTANT]
> If you have not yet followed
> the [/IOTCONNECT quickstart guide for this board](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/stm32mp135f-dk/README.md),
> complete that first and then return here to pick up on Step 1

## 1. Clone This Git Repository to Your Host Machine

Clone a copy of this repo to your local PC. This is where you will make changes/additions to the demo files.
> [!NOTE]
> On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 2. Customize Package

Inside of the cloned repo (```iotc-python-lite-sdk-demos```), navigate to the ```stm32mp135f-dk/mkboxpro-demo/src/```
directory:

```
cd ./stm32mp135f-dk/mkboxpro-demo/src/
```

By default, this directory contains the necessary files to upgrade from the basic quickstart application to the MKBOXPRO
sensor pack demo. If this is all you wish to do with this package, you may move to step 3.

If you wish to achieve something other than that, you will need to modify, add, and/or remove files to/from ```src```
accordingly.

## 3. Create Package

Navigate back to the ```mkboxpro-demo``` directory and then run this command to create ```package.tar.gz``` which
includes the necessary demo files and installation script:

```
bash ./create-package.sh
```

> [!NOTE]
> At the end of the package creation script, ```package.tar.gz``` is automatically copied into the ```common```
> directory so it can be readily accessed by the scripts used in optional steps 5B and 5C.

## 4. Prepare Device to Receive Package

> [!IMPORTANT]
> Upgrading from the basic quickstart demo to the MKBOXPRO demo requires a template change (to `mkboxpro`) for the
> device in /IOTCONNECT. If you send the package via OTA or command from your host PC, this is taken care of during that
> process. If you are sending the package through a local file transfer or through an OTA via the /IOTCONNECT online
> platform, you will have to manually change your device's template on your device's page in the online /IOTCONNECT
> platform.

For your board to receive the package through /IOTCONNECT, it must be actively connected. Do this by running the main
/IOTCONNECT program on your board called ```app.py```:

From here, you have the option to push the package to your devices directly to your device in one of the following ways:

### 5A. Deliver Package Through Local File Transfer

To deliver your package to a device through a local file transfer, the recommended method is to use an ```scp``` (secure
copy) command.

First find the active IP address of your device and then use that IP address to copy ```package.tar.gz``` into the main
application directory of the device (```/home/weston/demo```).

After the file transfer is complete, open a terminal on your device, navigate to the main application directory, and
verify that there is a ```package.tar.gz``` present.

If ```package.tar.gz``` is there, run this command to decompress the file and overwrite existing files in the directory:

```
tar -xzf package.tar.gz --overwrite
```

Lastly, execute the ```install.sh``` script to perform any additional file movements/modifications that you programmed
into your install package:

```
bash ./install.sh
```

### 5B. Upload and Push Package Through OTA in /IOTCONNECT Online Platform

1) In the "Device" Page of the online /IOTCONNECT platform, on the blue toolbar at the bottom of the page select "
   Firmware"
2) If a firmware has already been created for your device's template, skip to step 3. Otherwise:
    * Select the blue "Create Firmware" button in the top-right of the screen
    * Name your firmware (remember this name for later)
    * Select your device's template from the "Template" drop-down (if your device's template is not in the list, a
      firmware for it already exists in your /IOTCONNECT instance)
    * Enter hardware and software version numbers (can be arbitrary such as 0, 0)
    * Select the "Browse" button in the "File" section and select your ```package.tar.gz```
    * Add descriptions if you desire
    * Select the "Save" button
3) Navigate back to the Firmware page and find your new firmware name in the list
4) Under the "Draft" column within the "Software Upgrades" column, click on the draft number (will be "1" for
   newly-created firmwares)
5) Select the black square with the black arrow under "Actions" to publish your firmware and make it available for OTA
6) In the "Firmware" page of /IOTCONNECT, select the "OTA Updates" button in the top-right of the screen
7) For "Hardware Version" select your firmware's name with the hyphenated hardware version from the drop-down
8) Select the software version you chose for your firmware
9) For "Target" select "Devices" from the drop-down
10) Select your device's unique ID from the "Devices" drop-down
11) Click the blue "Update" button to initialize the OTA update

> [!NOTE]
> If you have obtained a solution key for your /IOTCONNECT account from Softweb Solutions, you can utilize the
> /IOTCONNECT REST API to automate the OTA deployment via 2 other methods outlined in [this guide](../../common/general-guides/REST-API-OTA.md)

## 6. View Update in Device Console

Shortly after sending the update via any method, you should see an interruption in the telemetry printout on the console
of your device informing you that an update package was received, downloaded and executed.

The program is designed to re-start itself after the update files have been automatically decompressed and the
```install.sh``` script is executed (if included). There is no need for you to do any manual reboots or file
manipulation. Your package installation is complete and the program is working again already!
