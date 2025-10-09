# /IOTCONNECT Python Lite SDK Demos Common Directory

This directory contains files that can be used across many (if not all) supported devices in this repository.

## General Guides

### REST-API-ONBOARD.md

This guide walks through the process of utilizing the /IOTCONNECT REST API to automate the device onboarding process for 
supported boards.

### UI-ONBOARD.md

This guide walks through the process of utilizing the /IOTCONNECT online user interface for the device onboarding process.

## Scripts

### cmd-package-send.py

This script is executed on a host PC to send a software package through a file-download command to one or more target
devices.

### device-setup.py

This script is downloaded and executed on a device to onboard the device into /IOTCONNECT, generate certificates and a
configuration file, and download the basic starter application.

### ota-package-send.py

This script is executed on a host PC to send a software package through an OTA update to one or more target devices.

## Templates

### AIMP1-template.json

This /IOTCONNECT template is used for devices that run the ST X-LINUX-AI Vision Demo, such as the STM32MP135F-DK.

### eiqIOTC-template.json

This /IOTCONNECT template is used for devices that run the NXP EIQ Vision AI DMS Demo, such as the NXP FRDM i.MX 93.

### mkboxpro-template.json

This /IOTCONNECT template is used for devices that run the MKBOXPRO Demo, such as the STM32MP157F-DK2.

### plitedemo-template.json

This is the basic /IOTCONNECT template for all devices running the starter demo.

### proteus-template.json

This /IOTCONNECT template is used for devices that run the standard PROTEUS Demo, such as the STM32MP157F-DK2.
