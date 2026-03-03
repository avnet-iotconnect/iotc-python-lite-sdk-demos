# Standard PROTEUS Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the STM32MP157F-DK2 to the standard PROTEUS sensor pack demo.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the STM32MP157F-DK2](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/stm32mp157f-dk2/README.md) before proceeding.

> [!IMPORTANT]
> This demo requires Python 3.12 (Scarthgap Yocto release). Verify your board is running a Scarthgap image before continuing.

> [!NOTE]
> Load your PROTEUS sensor pack with the correct firmware before running this demo by following the [PROTEUS setup guide](PROTEUS-SETUP.md).

## 1. Introduction

This demo streams environmental sensor telemetry from a PROTEUS sensor pack to /IOTCONNECT via the STM32MP157F-DK2. Sensor data appears in real time under the **Live Data** tab of your device in the /IOTCONNECT platform.

## 2. Change Device Template

Before installing, change your device's template to `proteus` in the /IOTCONNECT online platform:

1. Open [awspoc.iotconnect.io](https://awspoc.iotconnect.io) and navigate to your device's page.
2. Locate the **Template** field (mid-left on the page) and click the edit icon.
3. Select the `proteus` template from the drop-down and save.

> [!TIP]
> If the `proteus` template is not yet present in your /IOTCONNECT instance, import it from [proteus-template.json](proteus-template.json) via **Templates → Create Template → Import**.

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/stm32mp157f-dk2/proteus-standard-demo/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

### Run

```bash
python3 app.py
```

## 4. Using the Demo

Once running and connected to /IOTCONNECT, telemetry from the PROTEUS sensor pack streams to your device's **Live Data** tab. The sensor pack reports temperature, humidity, pressure, and other environmental readings.

## 5. Customize and Rebuild (Optional)

To modify the demo files before deploying:

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `stm32mp157f-dk2/proteus-standard-demo/src/` as needed.

3. Rebuild the package:
   ```bash
   cd stm32mp157f-dk2/proteus-standard-demo
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
   2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `proteus` template, set version numbers (e.g., `0`, `0`), browse to `package.tar.gz`, and click **Save**.
   3. Back on the Firmware page, click the draft number under **Software Upgrades → Draft**.
   4. Click the publish icon (black square with arrow) under **Actions**.
   5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to **Devices**, select your device, and click **Update**.

   Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically.
