# Introduction

This repository contains various guides and demos that utilize
the [/IOTCONNECT Python Lite SDK](https://github.com/avnet-iotconnect/iotc-python-lite-sdk) to connect devices to the
Avnet /IOTCONNECT platform and showcase telemetry reporting and cloud-to-device command functionality.
The Python Lite SDK may be used to enable /IOTCONNECT on a wide variety of development boards/platforms. Avnet has
completed this work for a subset of boards as outlined in the following section.

# Pre-Enabled Development Boards

The following development boards are pre-enabled with /IOTCONNECT in this repository:

* [Arduino Uno Q](arduino-uno-q) - ([Purchase Link](https://www.newark.com/arduino/abx00162/uno-q-sbc-2gb-arm-cortex-a53-m33f/dp/59AM1209))
* [Microchip Curiosity PIC64GX1000 Kit](microchip-pic64gx1000) - ([Purchase Link](https://www.newark.com/microchip/curiosity-pic64gx1000-kit/curiosity-kit-64bit-risc-v-quad/dp/46AM3917))
* [Microchip PolarFire SoC Discovery Kit](microchip-polarfire-soc-dk) - ([Purchase Link](https://www.newark.com/microchip/mpfs-disco-kit/discovery-kit-64bit-risc-v-polarfire/dp/97AK2474))
* [Microchip ATSAMA5D27-SOM1](microchip-sama5d27) - ([Purchase Link](https://www.newark.com/microchip/atsama5d27-som1-ek1/eval-board-32bit-mpu-arm-cortex/dp/44AC2213))
* [Microchip SAMA7D65 Curiosity Kit](microchip-sama7d65-curiosity) - ([Purchase Link](https://www.newark.com/microchip/ev63j76a/development-kit-arm-cortex-a7/dp/46AM2853))
* [NVIDIA Jetson Orin NX](nvidia-jetson-orin) - ([Purchase Link](https://www.newark.com/seeed-studio/110110144/recomputer-j4011-edge-ai-device/dp/74AK7856))
* [NXP FRDM-IMX93](nxp-frdm-imx-93) - ([Purchase Link](https://www.newark.com/nxp/frdm-imx93/dev-brd-64bit-arm-cortex-a55-m33/dp/20AM9538))
* [NXP GoldBox 3 Vehicle Networking Development Platform](nxp-s32g-vnp-gldbox3) - ([Purchase Link](https://www.newark.com/nxp/s32g-vnp-gldbox/ref-design-board-vehicle-n-w-processor/dp/37AJ9124))
* [Raspberry Pi](raspberry-pi) - ([Purchase Link](https://www.newark.com/raspberry-pi/rpi5-4gb-single/rpi-5-board-2-4ghz-4gb-arm-cortex/dp/81AK1346))
* [Renesas RZ/G3E Evaluation Board Kit](renesas-rzg3e-evk) - ([Purchase Link](https://www.newark.com/renesas/rtk9947e57s01000be/eval-kit-arm-cortex-a55-m33-64bit/dp/73AM7397))
* [ST STM32MP135F-DK Discovery Kit](stm32mp135f-dk) - ([Purchase Link](https://www.newark.com/stmicroelectronics/stm32mp135f-dk/discovery-kit-32bit-arm-cortex/dp/68AK9977))
* [ST STM32MP157F-DK2 Discovery Kit](stm32mp157f-dk2) - ([Purchase Link](https://www.newark.com/stmicroelectronics/stm32mp157f-dk2/discovery-board-32bit-arm-cortex/dp/14AJ2731))
* [ST STM32MP257F-DK Evaluation Board](stm32mp257f-dk) - ([Purchase Link](https://www.newark.com/stmicroelectronics/stm32mp257f-dk/discovery-board-arm-cortex-a35/dp/21AM3759))
* [ST STM32MP257F-EV1 Evaluation Board](stm32mp257f-ev1) - ([Purchase Link](https://www.newark.com/stmicroelectronics/stm32mp257f-ev1/eval-brd-arm-cortex-a35-m33-m0/dp/13AM6530))
* [Tria MaaXBoard 8M](tria-maaxboard-8m) - ([Purchase Link](https://www.newark.com/avnet/aes-mc-sbc-imx8m-g/sbc-i-mx-8m-arm-cortex-a53-m4f/dp/70AH4311))
* [Tria MaaXBoard 8ULP](tria-maaxboard-8ulp) - ([Purchase Link](https://www.newark.com/avnet/aes-maaxb-8ulp-sk-g/maaxboard-8ulp-sbc-arm-cortex/dp/87AK5106))
* [Tria MaaXBoard OSM93](tria-maaxboard-osm93) - ([Purchase Link](https://www.newark.com/avnet/aes-maaxb-osm93-dk-g/maaxboard-som-arm-cortex-a55-m33/dp/25AM3171))
* [Tria Vision AI-KIT 6490](tria-vision-ai-kit-6490) - ([Purchase Link](https://www.newark.com/avnet/sm2-sk-qcs6490-ep6-kit001/dev-kit-64bit-arm-cortex-a55-a78/dp/51AM9843))
* [Tria ZUBOARD-1CG](tria-zuboard-1cg) - ([Purchase Link](https://www.newark.com/avnet/aes-zub-1cg-dk-g/development-board-arm-cortex-a53/dp/41AK2454))

# Getting Started

To get started connecting your board to /IOTCONNECT, **first follow the Quickstart Guide within your board's specific
directory in this repository.** This guide will help you flash any required images, get access to your device's console,
and set up basic /IOTCONNECT onboarding for your device.

# AWS Greengrass Demos Enablement

To explore setting up AWS Greengrass Lite on some of these same devices and deploying Python demos through pre-built or custom
components, check out the [/IOTCONNECT Python Greengrass Demos repo](https://github.com/avnet-iotconnect/iotc-python-greengrass-demos/tree/main).

# Further Customization

If you want to modify or add onto the basic /IOTCONNECT starter application, you can do so by sending a software package
to your device.

Within the [common](./common) directory is a ```starter-demo``` directory with instructions on how to do this.

Some devices also include directories for pre-built expansion demos such as
the [EIQ Vision AI Driver Monitoring System (DMS) Demo](nxp-frdm-imx-93/dms-demo) for the NXP FRDM i.MX 93. Inside of
the directories for those demos you will find instructions on how to use a software package to deliver and install the
pre-built demo.

## Licensing

This library is distributed under
the [MIT License](https://github.com/avnet-iotconnect/iotc-c-lib/blob/master/LICENSE.md).
