# /IOTCONNECT Python Lite SDK Demos Common Directory

This directory contains files that can be used across many (if not all) supported devices in this repository.

## General Guides

### REST-API-ONBOARD.md

This guide walks through the process of utilizing the /IOTCONNECT REST API to automate the device onboarding process for 
supported boards.

### REST-API-OTA.md

This guide walks through additional OTA methods which utilize the /IOTCONNECT REST API to automate the deployment of software 
packages.

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

### quickstart.sh

This script is run to onboard devices for most devices in this repository and downloads the basic starter application afterwards.

## Starter Demo

This is the standard software package that all base quickstarts in this repository use. 

## Templates

### plitedemo-template.json

This is the basic /IOTCONNECT template for all devices running the starter demo. Expansion demo templates are located in their respective demo directories.
