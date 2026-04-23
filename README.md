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
* [ST STM32MP215F-DK Discovery Kit](stm32mp215f-dk) - ([Purchase Link](https://www.avnet.com/americas/product/stmicroelectronics/stm32mp215f-dk/evolve-151041109/))
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

Some devices also include directories for pre-built expansion demos. Inside of the directories for those demos you will find instructions on how to use a software package to deliver and install the pre-built demo. The available expansion demos are described in the sections below.

# EIQ Vision AI Driver Monitoring System (DMS)

The EIQ DMS demo uses the NXP eIQ Vision AI stack to analyze a live camera feed for driver safety indicators. It detects facial attributes such as eye state, head pose, and drowsiness, and streams the results to /IOTCONNECT in real time. An HDMI display can optionally be connected to view the annotated video feed with AI overlay directly on the board.

**Supported on:**
* [NXP FRDM-IMX93](nxp-frdm-imx-93/dms-demo/README.md)
* [Tria MaaXBoard OSM93](tria-maaxboard-osm93/dms-demo/README.md)

# X-LINUX-AI Object Detection

The X-LINUX-AI vision demo runs an on-device object detection model using ST's X-LINUX-AI software stack. It recognizes 80 common object categories from a connected USB camera and streams detected object names with confidence percentages to /IOTCONNECT approximately once per second.

**Supported on:**
* [ST STM32MP135F-DK Discovery Kit](stm32mp135f-dk/ai-vision/README.md)
* [ST STM32MP157F-DK2 Discovery Kit](stm32mp157f-dk2/ai-vision/README.md)

# MKBOXPRO BLE Sensor Pack

The MKBOXPRO demo streams live BLE sensor telemetry from a SensorTile.box PRO (MKBOXPRO) sensor pack to /IOTCONNECT. The SensorTile.box PRO connects wirelessly to the host board over Bluetooth Low Energy and provides multi-axis motion, environmental, and audio sensor data, all visible in real time on the /IOTCONNECT platform's Live Data tab.

**Supported on:**
* [ST STM32MP135F-DK Discovery Kit](stm32mp135f-dk/mkboxpro-demo/README.md)
* [ST STM32MP157F-DK2 Discovery Kit](stm32mp157f-dk2/mkboxpro-demo/README.md)
* [ST STM32MP257F-DK Evaluation Board](stm32mp257f-dk/mkboxpro-demo/README.md)

# PROTEUS Sensor Pack

The PROTEUS demo streams environmental sensor telemetry from a PROTEUS sensor pack to /IOTCONNECT. The PROTEUS pack provides temperature, humidity, pressure, and other environmental readings that appear in real time under the Live Data tab of your device in the /IOTCONNECT platform.

**Supported on:**
* [ST STM32MP135F-DK Discovery Kit](stm32mp135f-dk/proteus-standard-demo/README.md)
* [ST STM32MP157F-DK2 Discovery Kit](stm32mp157f-dk2/proteus-standard-demo/README.md)
* [ST STM32MP257F-DK Evaluation Board](stm32mp257f-dk/proteus-standard-demo/README.md)

# File Upload Demo

The file upload demo captures still pictures and fixed-length video clips from a USB camera, stores them locally on the board, and uploads the completed media files to the device's S3-backed /IOTCONNECT file-support bucket via the SDK. On-demand picture capture and rolling video clip recording are both triggered through /IOTCONNECT commands.

**Supported on:**
* [NXP FRDM-IMX93](nxp-frdm-imx-93/file-upload-demo/README.md)

# FPGA ML Acceleration (Microchip PolarFire SoC)

These demos leverage the FPGA fabric on Microchip PolarFire SoC boards to accelerate machine learning inference on waveform classification tasks. Each demo compares software vs. FPGA-hardware performance by running the same inference in both modes and reporting timing and prediction telemetry to /IOTCONNECT. Three demos are available with increasing model complexity:

## Template Correlation Classifier

A deterministic classifier with no neural network or training step. Classification works by correlating 256-sample input waveforms against hand-crafted reference templates using dot products. Because the algorithm is lightweight, this demo establishes a clear performance baseline before introducing learned models.

**Supported on:**
* [Microchip PolarFire SoC Discovery Kit](microchip-polarfire-soc-dk/ml-template-correlation-classifier/README.md)
* [Microchip PolarFire SoC Video Kit](microchip-polarfire-soc-vk/track1-iotc-ml-classifier/README.md)

## Simple Neural Network Accelerator

Introduces a compact fixed-point neural network in FPGA fabric (256 inputs → 12-node hidden layer → 6 classes, int8/int32 arithmetic). Hardware speedup over software is modest at small batch sizes but increases with larger batches, making it a focused demonstration of the neural network acceleration pipeline.

**Supported on:**
* [Microchip PolarFire SoC Discovery Kit](microchip-polarfire-soc-dk/ml-simple-nn-accelerator/README.md)
* [Microchip PolarFire SoC Video Kit](microchip-polarfire-soc-vk/track2-iotc-ml-nn-accelerator/README.md)

## Complex Neural Network Accelerator

The deepest model in the series — two hidden layers (~11K trained weights) with a batch-aware FPGA interface using DMA transfers. Hardware acceleration advantage is most measurable and consistent here, especially at moderate to large batch sizes.

**Supported on:**
* [Microchip PolarFire SoC Discovery Kit](microchip-polarfire-soc-dk/ml-complex-nn-accelerator/README.md)
* [Microchip PolarFire SoC Video Kit](microchip-polarfire-soc-vk/track3-iotc-ml-complex-accelerator/README.md)

# Tria Vision AI Demo

The Vision AI demo integrates with the Vision AI-KIT 6490's on-device AI inference pipeline to stream inference results and system status telemetry to /IOTCONNECT in real time. Supported AI tasks include Pose Detection, Object Detection, and Image Classification, with confidence scores reported per inference. The board can run two simultaneous AI demos when two cameras are connected.

**Supported on:**
* [Tria Vision AI-KIT 6490](tria-vision-ai-kit-6490/vision-ai/README.md)

# AWS Kinesis Video Streams (KVS)

[AWS Kinesis Video Streams (KVS)](https://aws.amazon.com/kinesis/video-streams/) is an AWS service for streaming video from devices to the cloud. The /IOTCONNECT platform integrates with KVS to enable live and recorded video directly from your device's dashboard. KVS expansion demos are available for a subset of the boards in this repository and are delivered as OTA software packages that patch on top of the basic /IOTCONNECT starter demo.

There are two types of KVS streaming, each suited to different use cases:

## KVS PutMedia

PutMedia streams video from the device to a KVS stream where it is stored and can be played back through the /IOTCONNECT dashboard. Because video is stored as fragments on AWS before playback begins, there is typically 5–15 seconds of end-to-end latency, but the footage is retained and can be reviewed after the fact. PutMedia is well-suited for security camera and recording use cases.

**Supported on:**
* [NVIDIA Jetson Orin NX](nvidia-jetson-orin/kvs-putmedia/README.md)
* [NXP FRDM-IMX93](nxp-frdm-imx-93/kvs-putmedia/README.md)
* [ST STM32MP135F-DK Discovery Kit](stm32mp135f-dk/kvs-putmedia/README.md)
* [ST STM32MP157F-DK2 Discovery Kit](stm32mp157f-dk2/kvs-putmedia/README.md)
* [ST STM32MP257F-DK Evaluation Board](stm32mp257f-dk/kvs-putmedia/README.md)
* [ST STM32MP257F-EV1 Evaluation Board](stm32mp257f-ev1/kvs-putmedia/README.md)
* [Tria Vision AI-KIT 6490](tria-vision-ai-kit-6490/kvs-putmedia/README.md)

## KVS WebRTC

WebRTC establishes a direct peer-to-peer connection between the device and the viewer's browser, brokered through a KVS signaling channel. This delivers sub-second latency, making it suitable for real-time monitoring. Unlike PutMedia, WebRTC video is not stored — it is only viewable while actively streaming.

**Supported on:**
* [NXP FRDM-IMX93](nxp-frdm-imx-93/kvs-webrtc/README.md)
* [ST STM32MP135F-DK Discovery Kit](stm32mp135f-dk/kvs-webrtc/README.md)
* [ST STM32MP157F-DK2 Discovery Kit](stm32mp157f-dk2/kvs-webrtc/README.md)
* [ST STM32MP257F-DK Evaluation Board](stm32mp257f-dk/kvs-webrtc/README.md)
* [ST STM32MP257F-EV1 Evaluation Board](stm32mp257f-ev1/kvs-webrtc/README.md)
* [Tria Vision AI-KIT 6490](tria-vision-ai-kit-6490/kvs-webrtc/README.md)

## Licensing

This library is distributed under
the [MIT License](https://github.com/avnet-iotconnect/iotc-c-lib/blob/master/LICENSE.md).
