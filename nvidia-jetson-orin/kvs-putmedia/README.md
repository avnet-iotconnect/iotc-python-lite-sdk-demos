# KVS PutMedia Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the NVIDIA Jetson Orin to the AWS Kinesis Video Streams (KVS) PutMedia video streaming demo.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Jetson Orin](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/nvidia-jetson-orin/README.md) before proceeding.

## 1. Introduction

This demo streams live video from a USB camera through the Jetson Orin to AWS Kinesis Video Streams (KVS), accessible via the /IOTCONNECT platform. The KVS Producer SDK is built from source on the board during installation — the first install takes approximately 15–20 minutes.

## 2. Set Up Hardware and Template

1. Plug a USB camera into a USB port on the Jetson Orin.

> [!TIP]
> Verify the camera is detected by running `ls /dev/video*` on the device. The app auto-detects the first available video device.

> [!IMPORTANT]
> This demo requires the `putmedia` template (available [here](putmedia-template.json)). If your device was created in /IOTCONNECT with the `plitedemo` template, change it to `putmedia` now via the edit icon next to the **Template** field on your device's page. If it was originally onboarded with `plitedemo`, the AWS backend may not register it for KVS — in that case, create a new device using the `putmedia` template.

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nvidia-jetson-orin/kvs-putmedia/package.tar.gz
tar -xzf package.tar.gz --overwrite
sudo bash ./install.sh
```

> [!IMPORTANT]
> `install.sh` requires root privileges — it installs system packages via `apt-get`, builds the KVS Producer SDK into `/opt/kvs-producer-sdk-cpp/`, and configures a system-wide `GST_PLUGIN_PATH` environment variable.

> [!NOTE]
> The first-time install takes approximately **15–20 minutes** due to the KVS Producer SDK build. Subsequent installs that do not rebuild the SDK complete much faster. Warning messages during installation are expected and can be ignored.

After `install.sh` completes, apply the new environment variable:

```bash
source /etc/profile.d/kvs-gstreamer.sh
```

Or log out and back in.

### Run

```bash
python3 app.py
```

## 4. Using the Demo

Once the application is running and connected to /IOTCONNECT:

- **Telemetry**: Sends a random integer and the current streaming status (true/false) every 10 seconds.
- **Auto-start**: If KVS is configured with auto-start in /IOTCONNECT, the video stream begins automatically 3 seconds after connecting.
- **Manual control**: Video streaming can be started/stopped via /IOTCONNECT commands from the device's **Video Streaming** tab. A **Start** button appears when streaming is off; a **Stop** button appears when streaming is active.

> [!IMPORTANT]
> For OTA-triggered installs, `app.py` must be running with root privileges (`sudo python3 app.py`) so that `install.sh` can install system packages and build the KVS SDK.

### Camera Configuration

The default camera settings in `app.py` are:
- Resolution: 640×480
- Framerate: 30 fps

These can be adjusted by modifying the `camera_options` dictionary in `app.py`.

## 5. Customize and Rebuild (Optional)

To modify the demo files before deploying:

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `nvidia-jetson-orin/kvs-putmedia/src/` as needed.

3. Rebuild the package:
   ```bash
   cd nvidia-jetson-orin/kvs-putmedia
   bash ./create-package.sh
   ```

4. Deliver the new package to the board:

   **Option A — Direct copy (scp):**
   ```bash
   # On host:
   scp package.tar.gz root@<board-ip>:/opt/demo/
   # On board:
   cd /opt/demo && tar -xzf package.tar.gz --overwrite && sudo bash ./install.sh
   ```

   **Option B — OTA via /IOTCONNECT platform:**
   1. In the **Device** page, select **Firmware** on the bottom toolbar.
   2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `putmedia` template, set version numbers (e.g., `0`, `0`), browse to `package.tar.gz`, and click **Save**.
   3. Back on the Firmware page, click the draft number under **Software Upgrades → Draft**.
   4. Click the publish icon (black square with arrow) under **Actions**.
   5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to **Devices**, select your device, and click **Update**.

   Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically. The first OTA install will take 15–20 minutes due to the SDK build.
