# Introduction
This document will help you create and deploy an OTA package for the FRDM i.MX 93 Development Board's DMS IoTConnect Demo. Via this OTA, you can automatically update the:
* Main IoTConnect program (imx93-ai-demo.py)
* Auxiliary AI DMS processing program (dms-processing.py)
* TFLITE models used by the AI program

# Create Updated Files
The first step is to actually make your desired changes to the files. You can download copies of *imx93-ai-demo.py* and *dms-processing.py* from this repository and then make your changes on your host machine. TFLITE models can be downloaded from numerous websites, but make sure they are compatible with the DMS demo. Alternatively, for a custom application you could train your own models.
>[!IMPORTANT]
>When making changes to *imx93-ai-demo.py* and *dms-processing.py*, make sure you save them under the exact same file name as the originals. Model files can have any name as long as they have a ".tflite" file extension.

# Download OTA Package Installation Script
[example](https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/nxp-frdm-imx-93/dms-demo/scripts/install.sh)

# Gather and Zip OTA Package
