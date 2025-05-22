# IoTConnect Python Lite SDK Demos Common Directory
This directory contains scripts and templates that can be used in the device setup process as well as the software package creation process across many (if not all) supported devices in this repository.

## Scripts

### cmd-package-send.py
This script is executed on a host PC to send a software package through a file-download command to one or more target devices. 

### device-setup.py
This script is downloaded and executed on a device to onboard the device into IoTConnect, generate certificates and a configuration file, and download the basic starter application.

### ota-package-send.py
This script is executed on a host PC to send a software package through an OTA update to one or more target devices. 

## Templates

### AIMP1-template.json
This IoTConnect template is used for devices that run the ST X-LINUX-AI Vision Demo, such as the STM32MP135F-DK.

### eiqIOTC-template.json
This IoTConnect template is used for devices that run the NXP EIQ Vision AI DMS Demo, such as the NXP FRDM i.MX 93.

### plitedemo-template.json
This is the basic IoTConnect template for all devices running the starter demo.
