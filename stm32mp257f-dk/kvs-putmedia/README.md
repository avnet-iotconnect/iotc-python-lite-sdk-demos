# KVS PutMedia Demo: Package Deployment

This guide will help you upgrade the basic /IOTCONNECT Starter Demo to the KVS PutMedia video streaming demo with a single update.

> [!IMPORTANT]
> If you have not yet followed
> the [/IOTCONNECT quickstart guide for this board](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/stm32mp257f-dk/README.md),
> complete that first and then return here to pick up on Step 1

## 1. Clone This Git Repository to Your Host Machine

Clone a copy of this repo to your local PC.
> [!NOTE]
> On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 2. Obtain the Package

A pre-built `package.tar.gz` is included in the `stm32mp257f-dk/kvs-putmedia/` directory of this repository. If using it, 
skip ahead to [Step 3](#3-prepare-device-to-receive-package).

<details>
<summary>Advanced: Build the Package Manually</summary>

If you need to rebuild the package (e.g., to pick up a newer version of the KVS Producer SDK or to modify the demo
files), you can cross-compile the SDK and create the package on your Linux host machine.

**Prerequisites:** Docker must be installed on your host machine.

**Step 1:** Cross-compile the KVS Producer SDK for aarch64 using Docker:

```
bash ~/kvs-build.sh
```

This will place the resulting `.so` library files in `~/kvs-libs/`. The build will take several minutes.

**Step 2:** Navigate to the demo directory and run the package creation script:

```
cd ./stm32mp257f-dk/kvs-putmedia
bash ./create-package.sh
```

This bundles the demo source files and the pre-built libraries into a new `package.tar.gz`, replacing the existing one.

</details>

## 3. Prepare Device to Receive Package

1) Plug your USB camera into a USB port on the STM32MP257F-DK

> [!TIP]
> You can verify the camera is detected by running ```ls /dev/video*``` on the device.
> The app will automatically identify USB cameras by inspecting the hardware path of each video device,
> so it will pick the correct one even if the board's onboard camera interfaces are also present.

>[!IMPORTANT]
> Ensure that when your device was onboarded into /IOTCONNECT that it was created with the `plitekvs` template 
> (available [here](../common/templates/plitekvs-template.json)), and then the Stream Type should 
> be "USB Based". The AWS backend will not register the device for KVS if it is created with the `plitedemo` template and 
> then later switched to `plitekvs`, it needs to be set at device creation.

## 3. Deploy Package to Device

For your board to receive the package through /IOTCONNECT, it must be actively connected. Do this by running the main
/IOTCONNECT program on your board called ```app.py```:

From here, you have the option to push the package to your device in one of the following ways:

### 3A. Deliver Package Through Local File Transfer

To deliver your package to a device through a local file transfer, the recommended method is to use an ```scp``` (secure
copy) command.

First find the active IP address of your device and then use that IP address to copy ```package.tar.gz``` into the main
application directory of the device (```/opt/demo```). The ```package.tar.gz``` file is located in the
```stm32mp257f-dk/kvs-putmedia/``` directory of this repository.

After the file transfer is complete, open a terminal on your device, navigate to the main application directory, and
verify that there is a ```package.tar.gz``` present.

If ```package.tar.gz``` is there, run this command to decompress the file and overwrite existing files in the directory:

```
tar -xzf package.tar.gz --overwrite
```

Lastly, execute the ```install.sh``` script to install the KVS libraries and configure the system:

```
bash ./install.sh
```

> [!NOTE]
> Warning messages in the console during the installation script are anticipated and can be ignored.

After install.sh completes, run the demo:

```
python3 app.py
```

### 3B. Upload and Push Package Through OTA in /IOTCONNECT Online Platform

1) In the "Device" Page of the online /IOTCONNECT platform, on the blue toolbar at the bottom of the page select "
   Firmware"
2) If a firmware has already been created for your device's template, skip to step 3. Otherwise:
    * Select the blue "Create Firmware" button in the top-right of the screen
    * Name your firmware (remember this name for later)
    * Select your device's template from the "Template" drop-down (if your device's template is not in the list, a
      firmware for it already exists in your /IOTCONNECT instance)
    * Enter hardware and software version numbers (can be arbitrary such as 0, 0)
    * Select the "Browse" button in the "File" section and select ```package.tar.gz``` from the
      ```stm32mp257f-dk/kvs-putmedia/``` directory of this repository
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
> Warning messages in the console during the installation script are anticipated and can be ignored.

> [!TIP]
> If you have obtained a solution key for your /IOTCONNECT account from Softweb Solutions, you can utilize the
> /IOTCONNECT REST API to automate the OTA deployment via 2 other methods outlined in [this guide](../../common/general-guides/REST-API-OTA.md)

## 4. View Update in Device Console

Shortly after sending the update via any method, you should see an interruption in the telemetry printout on the console
of your device informing you that an update package was received, downloaded and executed.

The program is designed to re-start itself after the update files have been automatically decompressed and the
```install.sh``` script is executed (if included). There is no need for you to do any manual reboots or file
manipulation. Your package installation is complete and the program is working again already!

> [!NOTE]
> Because the KVS libraries are pre-built and bundled in the package, installation on the STM32MP257F-DK is fast
> — there is no on-device compilation step.

## 5. Using the KVS PutMedia Demo

Once the application is running and connected to /IOTCONNECT, the demo operates as follows:

* **Telemetry**: Sends a random integer and the current streaming status (true/false) every 10 seconds
* **Auto-start**: If KVS is configured with auto-start in /IOTCONNECT, the video stream will begin automatically 3 seconds after connecting
* **Manual control**: Video streaming can be started/stopped via /IOTCONNECT commands from the device's Video Streaming tab. If Video Streaming
  is currently off, a "Start" button on the page can be pressed which sends the "Start Streaming" command to the device. If Video Streaming is
  currently on, a "Stop" button on the page can be pressed which sends the "Stop Streaming" command to the device.

### Camera Configuration

The default camera settings in ```app.py``` are:
* Resolution: 640x480
* Framerate: 30 fps

These can be adjusted by modifying the ```camera_options``` dictionary in ```app.py```.
