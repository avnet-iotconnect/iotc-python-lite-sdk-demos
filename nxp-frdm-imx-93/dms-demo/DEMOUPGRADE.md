# Upgrading from Basic Demo to AI DMS Demo
This guide will help you upgrade the basic IoTConnect Quickstart Demo (random-integer telemetry) to the Driver Monitoring System AI Demo with a single OTA update. The resulting demo will run default model files. After completing the steps in this guide, if you want to modify the demo to include custom model files, check out [this other guide].

>[!IMPORTANT]
> If you have not yet followed the [IoTConnect quickstart guide for this board](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/nxp-frdm-imx-93/README.md), complete that first and then return here to pick up on Step 1

## 1. Clone This Git Repository to Your Host Machine
Clone a copy of this repo to your local PC. This is where you will make changes/additions to the demo files.
>[!NOTE]
>On a Linux machine this can simply be done in the terminal, but a Windows host machine will require Git Bash or WSL.

## 2. Arrange Files and Create OTA Payload
Inside of the cloned repo, navigate to the ```scripts``` folder in this directory:
```
cd ./nxp-frdm-imx-93/dms-demo/scripts
```
Then run this command to move the Driver Monitoring System AI Demo files into the correct folder for creating an OTA upgrade package:
```
bash ./move-files.sh
```
Then run these commands to create the compressed OTA package:
```
cd ../../../files/ota-files
bash ./generate-payload.sh
```
Inside of the ```ota-files``` directory you should now see a file called ```ota-payload.tar.gz```

## 3. Send the OTA Update
Run this command to commence the OTA process:
```
python3 ota-update.py
```
You will be prompted to enter the unique ID of your device, and then asked if there are other devices this OTA should be sent to as well. 

You will then be notified that the template for your device is "plitedemo" and asked if you want to change it. Respond "Y" and then after the resulting prompt enter the template code ```eiqIOTC```

You may get a notification that the eiqIOTC template already has firmware on your entity, and that an upgrade will be created for it. No action needs to be taken by you.

You should see this output when the OTA upgrade has been pushed:
```
Successful OTA push!
```
