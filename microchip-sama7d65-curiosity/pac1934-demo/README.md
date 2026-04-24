# PAC1934 Power Monitoring Demo

Upgrades the /IOTCONNECT Starter Demo on the Microchip SAMA7D65-Curiosity Kit to read voltage, current, and power measurements from the on-board PAC1934 power monitor IC and publish them to /IOTCONNECT.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Microchip SAMA7D65-Curiosity Kit](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/microchip-sama7d65-curiosity/README.md) before proceeding.

## 1. Introduction

The SAMA7D65-Curiosity Kit includes an on-board **Microchip PAC1934** four-channel DC power/energy monitor connected via I2C. The PAC1934 measures voltage, current, and power across four internal power rails without requiring any additional external hardware:

| Channel | Power Rail | Description |
|---------|------------|-------------|
| 1 | VDD_3V3 | 3.3V general-purpose supply |
| 2 | VDD_DDR_IO | DDR memory and I/O supply |
| 3 | VDDCORE | MPU core voltage |
| 4 | VDD_CPU | CPU supply |

This demo reads these measurements over I2C from the Linux userspace and sends them as telemetry to /IOTCONNECT. It is based on the [Microchip SAMA7D65 Curiosity Power Monitoring Application Note](https://developerhelp.microchip.com/xwiki/bin/view/software-tools/mcu-dev-boards/32-bit-kits/sama7d65-curiosity/power-monitoring/).

## 2. Set Up Hardware

> [!IMPORTANT]
> Jumpers **J6** and **J7** must be set to the **MPU selection** position (pins **2-3** closed) so that the SAMA7D65 MPU can access the PAC1934 over I2C. This is the **opposite** of the default setting described in the Microchip application note, which uses pins 1-2 for the external Windows GUI tool.
>
> - **J6**: Close pins **2-3** (MPU I2C)
> - **J7**: Close pins **2-3** (MPU I2C)
>
> If pins 1-2 are closed instead, the PAC1934 I2C bus is routed to the external USB connector (J5) and the MPU will not be able to communicate with it.

No additional cables or peripherals are needed. The PAC1934 is already wired on the board. Complete the same physical connections as the quickstart guide (USB-C power, Ethernet, SD card, serial adapter).

## 3. Change Device Template

1. Import the [pac1934-template.json](./pac1934-template.json) device template to /IOTCONNECT and in your device's page, set the template to `sama7dPac`.

<img src="../media/new-template.png" alt="Setting the device template in /IOTCONNECT" width="400" />

The template defines telemetry attributes for all four channels (voltage, current, power per channel) and two commands: `set-interval` and `file-download`.

## 4. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/microchip-sama7d65-curiosity/pac1934-demo/packages/pac1934-package.tar.gz
tar -xzf pac1934-package.tar.gz --overwrite
bash ./install.sh
```

### Run

```bash
cd /opt/demo
python3 app.py
```

The application will initialize the PAC1934 over I2C, connect to /IOTCONNECT, read all four power channels every 10 seconds by default, and publish telemetry. View the power monitoring data under the **Live Data** tab for your device on /IOTCONNECT.

## 5. Demo Variants

Four application scripts are provided to monitor all channels or individual subsets:

| Script | Channels Monitored | Description |
|--------|-------------------|-------------|
| `app.py` | All 4 (CH1–CH4) | Full power monitoring of all rails |
| `app_ch3.py` | Channel 3 only (VDDCORE) | Core voltage monitoring only |
| `app_ch4.py` | Channel 4 only (VDD_CPU) | CPU voltage monitoring only |
| `app_ch3_4.py` | Channels 3 & 4 (VDDCORE + CPU) | Core and CPU monitoring |

Run any variant the same way:

```bash
python3 app_ch3.py
python3 app_ch4.py
python3 app_ch3_4.py
```

> [!NOTE]
> Single-channel and dual-channel variants send only the relevant telemetry fields. The /IOTCONNECT template will show `null` for channels that are not being reported. You can use the same `sama7dPac` template for all variants.

## 6. Telemetry

Each telemetry message includes `sdk_version` and `telemetry_interval`, plus per-channel measurements:

| Field | Unit | Description |
|-------|------|-------------|
| `vdd_3v3_vbus_mv` | mV | VDD 3.3V bus voltage |
| `vdd_3v3_isense_ma` | mA | VDD 3.3V current |
| `vdd_3v3_power_mw` | mW | VDD 3.3V power |
| `vdd_ddr_io_vbus_mv` | mV | DDR/IO bus voltage |
| `vdd_ddr_io_isense_ma` | mA | DDR/IO current |
| `vdd_ddr_io_power_mw` | mW | DDR/IO power |
| `vddcore_vbus_mv` | mV | Core bus voltage |
| `vddcore_isense_ma` | mA | Core current |
| `vddcore_power_mw` | mW | Core power |
| `vdd_cpu_vbus_mv` | mV | CPU bus voltage |
| `vdd_cpu_isense_ma` | mA | CPU current |
| `vdd_cpu_power_mw` | mW | CPU power |

Typical measurements at 800 MHz CPU clock (from the Microchip application note):

| Rail | Voltage | Current |
|------|---------|---------|
| VDD_3V3 | ~3300 mV | ~82 mA |
| VDDCORE | ~800 mV | ~168 mA |
| VDD_CPU | ~800 mV | ~99 mA |

## 7. Commands

| Command | Description |
|---------|-------------|
| `set-interval` | Change the telemetry reporting interval at runtime (seconds). Example: `set-interval 5` |
| `file-download` | Download and install a replacement application package from a URL, then restart |

## 8. Environment Overrides

```bash
export PAC_CONFIG_DIR=/opt/demo   # Directory containing iotcDeviceConfig.json and certs
export PAC_TELEMETRY_SECS=10      # Telemetry interval in seconds (default: 10)
```

## 9. Resources

- [Microchip SAMA7D65 Curiosity Power Monitoring Application Note](https://developerhelp.microchip.com/xwiki/bin/view/software-tools/mcu-dev-boards/32-bit-kits/sama7d65-curiosity/power-monitoring/)
- [PAC1934 Product Page](https://www.microchip.com/en-us/product/pac1934)
- [/IOTCONNECT Quickstart for SAMA7D65](../README.md)
