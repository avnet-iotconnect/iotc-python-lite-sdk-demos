# Introduction
This repository contains various guides and demos that utilize the [/IOTCONNECT Python Lite SDK](https://github.com/avnet-iotconnect/iotc-python-lite-sdk) to connect devices to the Avnet /IOTCONNECT platform and showcase telemetry reporting and cloud-to-device command functionality.
The Python Lite SDK may be used to enable /IOTCONNECT on a wide variety of development boards/platforms.  Avnet has completed this work for a subset of board as outlined in the following section.

# Pre-Enabled Development Boards
The following development boards are pre-enabled with /IOTCONNECT in this repository:

* [Microchip ATSAMA5D27-SOM1](microchip-sama5d27) - ([Product Link](https://www.microchip.com/en-us/product/atsama5d27-som1))
* [NXP FRDM-IMX93](nxp-frdm-imx-93) - ([Product Link](https://www.avnet.com/shop/us/products/nxp/frdm-imx93-3074457345660216004/))
* [ST STM32MP157F-DK2 Discovery Kit](stm32mp157f-dk2) - ([Product Link](https://www.st.com/en/evaluation-tools/stm32mp157f-dk2.html))
* [ST STM32MP257F-EV1 Evaluation Board](stm32mp257f-ev1) - ([Product Link](https://www.st.com/en/evaluation-tools/stm32mp257f-ev1.html))
* [ST STM32MP135F-DK Discovery Kit](stm32mp135f-dk) - ([Product Link](https://www.st.com/en/evaluation-tools/stm32mp135f-dk.html))
* [Tria MaaXBoard OSM93](tria-maaxboard-osm93) - ([Product Link](https://www.tria-technologies.com/product/maaxboard-osm93/))
* [Tria MaaXBoard 8ULP](tria-maaxboard-8ulp) - ([Product Link](https://www.tria-technologies.com/product/maaxboard-8ulp/))

# Getting Started
To get started connecting your board to IoTConnect, **first follow the Quickstart Guide within your board's specific directory in this repository.** This guide will help you flash any required images, get access to your device's console, and set up basic IoTConnect onboarding for your device.

# Further Customization
If you want to modify or add onto the basic IoTConnect starter application, you can do so by sending an installation package to your device. Check out the [package creation and deployment guide](./package-create-and-deploy/README.md) for instructions on how to do this. 

## Licensing

This library is distributed under the [MIT License](https://github.com/avnet-iotconnect/iotc-c-lib/blob/master/LICENSE.md).
