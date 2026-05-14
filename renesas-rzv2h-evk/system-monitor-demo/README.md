# RZ/V2H EVK — System Monitor Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the Renesas RZ/V2H EVK to the System Monitor Demo, which streams real-time system 
performance telemetry: CPU utilisation, RAM usage, and CPU temperatures read directly from the Linux kernel's `/proc` and 
`/sys` interfaces.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the RZ/V2H EVK](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/renesas-rzv2h-evk/README.md) 
> before proceeding.

## 1. Introduction

This demo streams live system performance data from the RZ/V2H EVK to /IOTCONNECT every 10 seconds. No additional 
hardware or packages beyond the IoTConnect SDK are required.

## 2. Change Device Template

Before installing, change your device's template to `rzv2h-system-monitor` in the /IOTCONNECT online platform:

1. Open your /IOTCONNECT instance and navigate to your device's page.
2. Locate the **Template** field and click the edit icon.
3. Select the `rzv2h-system-monitor` template from the drop-down and save.

> [!TIP]
> If the `rzv2h-system-monitor` template is not yet present in your /IOTCONNECT instance, import it from 
> [rzv2h-system-monitor-template.json](rzv2h-system-monitor-template.json) via **Templates → Create Template → Import**.

## 3. Download and Install

On the board, run:

```bash
cd /opt/demo
wget -O package.tar.gz https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/renesas-rzv2h-evk/system-monitor-demo/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

## 4. Using the Demo

```bash
cd /opt/demo
python3 app.py
```

Once running and connected to /IOTCONNECT, telemetry streams to your device's **Live Data** tab every 10 seconds:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sdk_version` | STRING | IoTConnect SDK version |
| `cpu_percent` | DECIMAL | CPU utilisation (%) |
| `memory_percent` | DECIMAL | RAM usage (%) |
| `cpu_temp_0_c` | DECIMAL | CPU cluster 0 temperature (°C) |
| `cpu_temp_1_c` | DECIMAL | CPU cluster 1 temperature (°C) |
| `random` | INTEGER | Random integer (connectivity heartbeat) |

### Commands

| Command | Parameter | Description |
|---------|-----------|-------------|
| `file-download` | URL | Download and apply an OTA update package |

## 5. Customize and Rebuild (Optional)

To modify the demo files before deploying:

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `renesas-rzv2h-evk/system-monitor-demo/src/` as needed.

3. Rebuild the package:
   ```bash
   cd renesas-rzv2h-evk/system-monitor-demo
   bash ./create-package.sh
   ```

4. Deliver the new package to the board:

   **Option A — Direct copy (scp):**
   ```bash
   # On host:
   scp package.tar.gz root@<board-ip>:/opt/demo/
   # On board:
   cd /opt/demo && tar -xzf package.tar.gz --overwrite && bash ./install.sh
   ```

   **Option B — OTA via /IOTCONNECT platform:**
   1. In the **Device** page, select **Firmware** on the bottom toolbar.
   2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `rzv2h-system-monitor` template, set version numbers (e.g., `0`, `0`), browse to `package.tar.gz`, and click **Save**.
   3. Back on the Firmware page, click the draft number under **Software Upgrades → Draft**.
   4. Click the publish icon (black square with arrow) under **Actions**.
   5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to **Devices**, select your device, and click **Update**.

   Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically.
