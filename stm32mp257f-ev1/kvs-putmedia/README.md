# KVS PutMedia Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the STM32MP257F-EV1 to the AWS Kinesis Video Streams (KVS) PutMedia video streaming demo.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the STM32MP257F-EV1](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/stm32mp257f-ev1/README.md) before proceeding.

## 1. Introduction

This demo streams live video from a USB camera through the STM32MP257F-EV1 to AWS Kinesis Video Streams (KVS), accessible via the /IOTCONNECT platform. The KVS Producer SDK libraries are pre-built and bundled in the package — no on-device compilation is required.

## 2. Set Up Hardware and Template

1. Plug a USB camera into a USB port on the STM32MP257F-EV1.

> [!TIP]
> Verify the camera is detected by running `ls /dev/video*` on the device. The app automatically identifies USB cameras by inspecting the hardware path of each video device, so it picks the correct one even if onboard camera interfaces are also present.

> [!IMPORTANT]
> This demo requires the `plitekvs` template (available [here](plitekvs-template.json)). The device **must be created in /IOTCONNECT with the `plitekvs` template** — the AWS backend will not register a device for KVS if it was originally created with the `plitedemo` template and later switched. If your device was created with `plitedemo`, create a new device using `plitekvs`.

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/stm32mp257f-ev1/kvs-putmedia/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

> [!NOTE]
> Warning messages in the console during the installation script are expected and can be ignored.

### Run

```bash
python3 app.py
```

## 4. Using the Demo

Once the application is running and connected to /IOTCONNECT:

- **Telemetry**: Sends a random integer and the current streaming status (true/false) every 10 seconds.
- **Auto-start**: If KVS is configured with auto-start in /IOTCONNECT, the video stream begins automatically 3 seconds after connecting.
- **Manual control**: Video streaming can be started/stopped via /IOTCONNECT commands from the device's **Video Streaming** tab. A **Start** button appears when streaming is off; a **Stop** button appears when streaming is active.

### Camera Configuration

The default camera settings in `app.py` are:
- Resolution: 640×480
- Framerate: 30 fps

These can be adjusted by modifying the `camera_options` dictionary in `app.py`.

## 5. Customize and Rebuild (Optional)

To modify the demo files before deploying, or to rebuild the package with a newer version of the KVS Producer SDK:

### Modify Source Files

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `stm32mp257f-ev1/kvs-putmedia/src/` as needed.

3. To rebuild with the existing pre-built libraries, run:
   ```bash
   cd stm32mp257f-ev1/kvs-putmedia
   bash ./create-package.sh
   ```

### Rebuild KVS Producer SDK (Advanced)

If you need to pick up a newer version of the KVS Producer SDK, cross-compile it on a Linux host using Docker:

**Prerequisites:** Docker must be installed on your host machine.

**Step 1:** Cross-compile the KVS Producer SDK for aarch64:
```bash
bash ~/kvs-build.sh
```
This places the resulting `.so` library files in `~/kvs-libs/`. The build takes several minutes.

**Step 2:** Rebuild the package (bundles the new libraries alongside the source files):
```bash
cd stm32mp257f-ev1/kvs-putmedia
bash ./create-package.sh
```

### Deliver the New Package

**Option A — Direct copy (scp):**
```bash
# On host:
scp package.tar.gz root@<board-ip>:/opt/demo/
# On board:
cd /opt/demo && tar -xzf package.tar.gz --overwrite && bash ./install.sh
```

**Option B — OTA via /IOTCONNECT platform:**
1. In the **Device** page, select **Firmware** on the bottom toolbar.
2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `plitekvs` template, set version numbers (e.g., `0`, `0`), browse to `package.tar.gz`, and click **Save**.
3. Back on the Firmware page, click the draft number under **Software Upgrades → Draft**.
4. Click the publish icon (black square with arrow) under **Actions**.
5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to **Devices**, select your device, and click **Update**.

> [!NOTE]
> Warning messages in the console during the installation script are expected and can be ignored.

Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically.
