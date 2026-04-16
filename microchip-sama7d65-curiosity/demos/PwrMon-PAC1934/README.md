# PAC1934 Power Monitoring Demo

Reads voltage, current, and power measurements from the on-board PAC1934 power monitor IC on the Microchip SAMA7D65-Curiosity Kit and publishes telemetry to /IOTCONNECT.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Microchip SAMA7D65-Curiosity Kit](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/microchip-sama7d65-curiosity/README.md) before proceeding.

1. [Introduction](#1-introduction)
2. [Hardware Setup](#2-hardware-setup)
3. [Set Up Template](#3-set-up-template)
4. [Deploy and Run](#4-deploy-and-run)
5. [Demo Variants](#5-demo-variants)
6. [Telemetry](#6-telemetry)
7. [Commands](#7-commands)
8. [Environment Overrides](#8-environment-overrides)
9. [Resources](#9-resources)

## 1. Introduction

The SAMA7D65-Curiosity Kit includes an on-board **Microchip PAC1934** four-channel DC power/energy monitor connected via I2C. The PAC1934 measures voltage, current, and power across four internal power rails without requiring any additional external hardware:

| Channel | Power Rail    | Description                          |
|---------|---------------|--------------------------------------|
| 1       | VDD_3V3       | 3.3V general-purpose supply          |
| 2       | VDD_DDR_IO    | DDR memory and I/O supply            |
| 3       | VDDCORE       | MPU core voltage                     |
| 4       | VDD_CPU       | CPU supply                           |

This demo reads these measurements over I2C from the Linux userspace and sends them as telemetry to /IOTCONNECT for cloud-based monitoring and visualization. Four Python application variants are provided so you can monitor all channels, individual channels, or a subset.

This demo is based on the [Microchip SAMA7D65 Curiosity Power Monitoring Application Note](https://developerhelp.microchip.com/xwiki/bin/view/software-tools/mcu-dev-boards/32-bit-kits/sama7d65-curiosity/power-monitoring/).

## 2. Hardware Setup

### Jumper Configuration (J6 and J7)

> [!IMPORTANT]
> The jumpers **J6** and **J7** must be set to the **MPU selection** position (pins **2-3** closed) so that the SAMA7D65 MPU can access the PAC1934 over I2C. This is the **opposite** of the default setting described in the Microchip application note, which uses pins 1-2 for the external Windows GUI tool.

Verify/set the jumpers:

- **J6**: Close pins **2-3** (MPU I2C)
- **J7**: Close pins **2-3** (MPU I2C)

If pins 1-2 are closed instead, the PAC1934 I2C bus is routed to the external USB connector (J5) for use with the Windows-based PAC193X GUI, and the MPU will **not** be able to communicate with the PAC1934.

### Other Connections

Follow the same hardware setup as the [quickstart guide](../../README.md#3-hardware-setup):

1. Connect USB-C cable to the board for power.
2. Connect Ethernet cable to your LAN.
3. Insert the SD card with the Yocto image.
4. Connect the USB to TTL Serial adapter to J35 for serial console access.

No additional cables or hardware are needed for this demo. The PAC1934 is already wired on the board.

## 3. Set Up Template

Create your device in /IOTCONNECT using the provided template:

1. Import [pac1934-template.json](./pac1934-template.json) into your /IOTCONNECT account.
2. The template code is `sama7dPac` (10-character limit on /IOTCONNECT template codes).

The template defines telemetry attributes for all four channels (voltage, current, power per channel) and two commands (`set-interval` and `file-download`).

Follow [this guide](../../../common/general-guides/UI-ONBOARD.md) to onboard the device.

## 4. Deploy and Run

### Install Dependencies

On the board, ensure the IoTConnect SDK and I2C support are installed:

```bash
sudo opkg update
python3 -m pip install --break-system-packages iotconnect-sdk-lite requests
```

> [!NOTE]
> The `--break-system-packages` flag is required because the Yocto image uses a PEP 668 externally-managed Python environment. If `iotconnect-sdk-lite` and `requests` were already installed during the [quickstart guide](../../README.md), no additional packages are needed. The PAC1934 driver reads from the kernel's IIO sysfs interface — no `smbus2` or other I2C library is required.

### Copy Application Files

From your host machine, copy the application files to the board:

```bash
scp src/py_pac193x.py src/app.py root@<board-ip>:/opt/demo/
```

Or, if you prefer to copy all demo variants at once:

```bash
scp src/*.py root@<board-ip>:/opt/demo/
```

### Run

```bash
cd /opt/demo
python3 app.py
```

The application will:
1. Initialize the PAC1934 over I2C.
2. Connect to /IOTCONNECT using the device identity files in the current directory.
3. Read all four power channels every 10 seconds (default).
4. Print measurements to the serial console.
5. Publish telemetry to /IOTCONNECT.

View the power monitoring data under the **Live Data** tab for your device on /IOTCONNECT.

## 5. Demo Variants

Four application scripts are provided to match the on-device demo scripts:

| Script         | Channels Monitored              | Description                                |
|----------------|--------------------------------|--------------------------------------------|
| `app.py`       | All 4 (CH1-CH4)               | Full power monitoring of all rails         |
| `app_ch3.py`   | Channel 3 only (VDDCORE)      | Core voltage monitoring only               |
| `app_ch4.py`   | Channel 4 only (VDD_CPU)      | CPU voltage monitoring only                |
| `app_ch3_4.py` | Channels 3 & 4 (VDDCORE + CPU)| Core and CPU monitoring                    |

Run any variant the same way:

```bash
python3 app_ch3.py       # Monitor VDDCORE only
python3 app_ch4.py       # Monitor VDD_CPU only
python3 app_ch3_4.py     # Monitor VDDCORE + VDD_CPU
```

> [!NOTE]
> The single-channel and dual-channel variants send only the relevant telemetry fields. The `/IOTCONNECT` template will show `null` or no data for the channels that are not being reported. You can use the same `sama7dPac` template for all variants.

## 6. Telemetry

Each telemetry message includes `sdk_version` and `telemetry_interval`, plus per-channel measurements:

| Field                    | Type    | Unit | Description                       |
|--------------------------|---------|------|-----------------------------------|
| `sdk_version`            | STRING  |      | IoTConnect SDK version            |
| `telemetry_interval`     | DECIMAL | s    | Current reporting interval        |
| `vdd_3v3_vbus_mv`       | DECIMAL | mV   | VDD 3.3V bus voltage              |
| `vdd_3v3_isense_ma`     | DECIMAL | mA   | VDD 3.3V current                  |
| `vdd_3v3_power_mw`      | DECIMAL | mW   | VDD 3.3V power                    |
| `vdd_ddr_io_vbus_mv`    | DECIMAL | mV   | DDR/IO bus voltage                |
| `vdd_ddr_io_isense_ma`  | DECIMAL | mA   | DDR/IO current                    |
| `vdd_ddr_io_power_mw`   | DECIMAL | mW   | DDR/IO power                      |
| `vddcore_vbus_mv`       | DECIMAL | mV   | Core bus voltage                  |
| `vddcore_isense_ma`     | DECIMAL | mA   | Core current                      |
| `vddcore_power_mw`      | DECIMAL | mW   | Core power                        |
| `vdd_cpu_vbus_mv`       | DECIMAL | mV   | CPU bus voltage                   |
| `vdd_cpu_isense_ma`     | DECIMAL | mA   | CPU current                       |
| `vdd_cpu_power_mw`      | DECIMAL | mW   | CPU power                         |

### Expected Values

Based on the Microchip application note, typical measurements at 800 MHz CPU clock:

| Rail       | Voltage  | Current   |
|------------|----------|-----------|
| VDD_3V3    | ~3300 mV | ~82 mA    |
| VDDCORE    | ~800 mV  | ~168 mA   |
| VDD_CPU    | ~800 mV  | ~99 mA    |

## 7. Commands

Commands can be sent from the /IOTCONNECT dashboard to the device:

- **`set-interval`**: Change the telemetry reporting interval at runtime. Argument: interval in seconds (positive number). Example: `set-interval 5` to report every 5 seconds.
- **`file-download`**: Download and install a replacement application package from a URL, then restart the app. Argument: URL string pointing to a `.tar.gz` package.

## 8. Environment Overrides

Configure the demo without editing the Python scripts:

```bash
export PAC_CONFIG_DIR=/opt/demo         # Directory containing iotcDeviceConfig.json and certs
export PAC_TELEMETRY_SECS=10            # Telemetry interval in seconds (default: 10)
```

`PAC_CONFIG_DIR` points to the directory containing:

- `iotcDeviceConfig.json`
- `device-cert.pem`
- `device-pkey.pem`

## 9. Resources

- [Microchip SAMA7D65 Curiosity Power Monitoring Application Note](https://developerhelp.microchip.com/xwiki/bin/view/software-tools/mcu-dev-boards/32-bit-kits/sama7d65-curiosity/power-monitoring/)
- [PAC1934 Product Page](https://www.microchip.com/en-us/product/pac1934)
- [Purchase the Microchip EV63J76A (SAMA7D65 Curiosity Kit)](https://www.newark.com/microchip/ev63j76a/development-kit-arm-cortex-a7/dp/46AM2853)
- [/IOTCONNECT Quickstart for SAMA7D65](../../README.md)
- [/IOTCONNECT Overview](https://www.iotconnect.io/)
- [/IOTCONNECT Knowledgebase](https://help.iotconnect.io/)
