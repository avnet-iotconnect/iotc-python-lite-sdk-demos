# KR260 System and Accelerator Monitor Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the AMD Kria KR260 to the Kria System and Accelerator Monitor Demo, which
streams system performance and SOM power telemetry and manages the programmable logic (PL) accelerator app from the
cloud through xmutil and dfx-mgr.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the KR260](../README.md) before proceeding.

## 1. Introduction

Every 10 seconds the demo publishes CPU utilisation, RAM usage, the three SOM die temperatures (AMS/SYSMON), and the
SOM 5V rail voltage, current, and power (INA260), along with the currently loaded PL accelerator app. Cloud commands
list, load, and unload accelerator apps through `xmutil`. The same demo runs on the KV260, KR260, and KD240 with one
shared device template; the app detects the board automatically.

## 2. Change Device Template

Before installing, change your device's template to `kriaSM` in the IOTCONNECT online platform:

1. Open your IOTCONNECT instance and navigate to your device's page.
2. Locate the **Template** field and click the edit icon.
3. Select the `kriaSM` template from the drop-down and save.

> [!TIP]
> If the `kriaSM` template is not yet present in your IOTCONNECT instance, import it from
> [kriaSM-template.json](kriaSM-template.json) via **Templates, Create Template, Import**.

## 3. Download and Install

On the board, run:

```bash
cd /opt/demo
wget -O package.tar.gz TODO-downloads.iotconnect.io-package-url
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

> [!NOTE]
> TODO: the package will be hosted on downloads.iotconnect.io; until then, build it yourself with the steps in
> section 6 and copy it to the board.

`install.sh` installs the Python dependencies and adds `/etc/sudoers.d/99-iotc-xmutil`, a rule that lets your user run
only the three `xmutil` invocations the demo issues (`listapps`, `loadapp`, `unloadapp`, each wrapped in a root-owned
`timeout`) without a password. The app-management cloud commands need that rule because the demo runs unprivileged.
Install the demo from an interactive shell the first time so the rule can be created; after that, OTA updates work
unattended. Remove the file to revoke the rule.

## 4. Using the Demo

```bash
cd /opt/demo
python3 app.py
```

To check the sensor readings without connecting to IOTCONNECT (no onboarding needed), run:

```bash
python3 app.py --dry-run
```

Once running and connected, telemetry streams to your device's **Live Data** tab every 10 seconds:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sdk_version` | STRING | IOTCONNECT SDK version |
| `board` | STRING | Kria starter kit id (kv260, kr260, kd240) |
| `cpu_percent` | DECIMAL | CPU utilisation (%) |
| `memory_percent` | DECIMAL | RAM usage (%) |
| `som_temp_ps_c` | DECIMAL | SOM PS die temperature (C) |
| `som_temp_rem_c` | DECIMAL | SOM remote die temperature (C) |
| `som_temp_pl_c` | DECIMAL | SOM PL die temperature (C) |
| `som_voltage_v` | DECIMAL | SOM 5V rail voltage (V) |
| `som_current_a` | DECIMAL | SOM 5V rail current (A) |
| `som_power_w` | DECIMAL | SOM power draw (W) |
| `loaded_app` | STRING | Currently loaded PL accelerator app, or `none` |
| `apps_installed` | STRING | Installed accelerator apps (JSON array) |
| `random` | INTEGER | Random integer (connectivity heartbeat) |

### Commands

| Command | Parameter | Description |
|---------|-----------|-------------|
| `list-apps` | none | Ack returns the installed accelerator apps and which one is loaded |
| `load-app` | app name | Loads the named accelerator app, unloading the current one first |
| `unload-app` | none | Unloads the currently loaded accelerator app |
| `file-download` | URL | Download and apply an OTA update package |

On a stock Ubuntu 24.04 image the installed apps are the default flat shells (`k26-starter-kits` on KV260/KR260,
`k24-starter-kits` on KD240). Additional apps installed from `ppa:xilinx-apps` (for example
`xlnx-firmware-kd240-motor-ctrl-qei`) appear automatically and can be switched from the cloud.

## 5. How It Works

* CPU and memory come from `/proc/stat` and `/proc/meminfo`.
* Temperatures come from the Zynq UltraScale+ AMS/SYSMON hwmon device (named `ams`); the stock Kria Ubuntu kernel
  exposes no `/sys/class/thermal` zones, so hwmon is read directly.
* SOM power comes from the INA260 power monitor on the SOM 5V rail (hwmon device `ina260_*`).
* Accelerator state comes from `sudo xmutil listapps`, which fronts the dfx-mgr daemon; `load-app` and `unload-app`
  shell out to `sudo xmutil loadapp` / `sudo xmutil unloadapp`.

## 6. Customize and Rebuild (Optional)

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `amd-kria-kr260/system-monitor-demo/src/` as needed.

3. Rebuild the package:
   ```bash
   cd amd-kria-kr260/system-monitor-demo
   bash ./create-package.sh
   ```

4. Deliver the new package to the board:

   **Option A, direct copy (scp):**
   ```bash
   # On host:
   scp package.tar.gz ubuntu@<board-ip>:/opt/demo/
   # On board:
   cd /opt/demo && tar -xzf package.tar.gz --overwrite && bash ./install.sh
   ```

   **Option B, OTA via the /IOTCONNECT platform:**
   1. In the **Device** page, select **Firmware** on the bottom toolbar.
   2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `kriaSM` template,
      set version numbers (for example `0`, `0`), browse to `package.tar.gz`, and click **Save**.
   3. Back on the Firmware page, click the draft number under **Software Upgrades, Draft**.
   4. Click the publish icon under **Actions**.
   5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to
      **Devices**, select your device, and click **Update**.

   Shortly after, the running `app.py` receives the package, decompresses it, executes `install.sh`, and restarts
   automatically.
