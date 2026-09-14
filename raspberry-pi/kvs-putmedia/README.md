# KVS PutMedia Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the Raspberry Pi (4 or 5) to the AWS Kinesis Video Streams (KVS) PutMedia video streaming demo.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Raspberry Pi](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/raspberry-pi/README.md) before proceeding.

## 1. Introduction

This demo streams live video from a USB camera through the Raspberry Pi to AWS Kinesis Video Streams (KVS), accessible via the /IOTCONNECT platform. The KVS Producer SDK is built from source on the board during installation — the first install takes approximately 15–20 minutes on a Pi 4, somewhat less on a Pi 5.

Neither the Raspberry Pi 4 (VideoCore VI) nor the Raspberry Pi 5 (VideoCore VII) expose a hardware H264 *encoder* via V4L2 (only hardware decode), so the USB camera's raw frames are re-encoded to H264 in software via GStreamer's `x264enc`, on the CPU. The default resolution is 640×480 at 30 fps, which both boards encode comfortably; the Pi 5's quad-core Cortex-A76 has ample headroom to go higher if desired.

## 2. Set Up Hardware and Template

1. Plug a USB camera into a USB port on the Raspberry Pi.

> [!TIP]
> Verify the camera is detected by running `ls /dev/video*` on the device. The board's own video hardware also registers `/dev/videoN` nodes, so the app identifies the USB camera specifically by inspecting the hardware path of each video device.

> [!IMPORTANT]
> This demo requires the `plitekvs` template (available [here](plitekvs-template.json)). The device must be created in /IOTCONNECT with the `plitekvs` template and the correct stream resource (Video Stream for a PutMedia stream or WebRTC for a WebRTC stream) must be selected during the device creation process. The AWS backend provisions a KVS WebRTC signaling channel for WebRTC devices and a KVS stream for PutMedia devices, and these cannot be switched after device creation. If your device was created with a different template, create a new device using `plitekvs` and select the appropriate stream resource.

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget -O package.tar.gz https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/raspberry-pi/kvs-putmedia/package.tar.gz
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

2. Edit files in `raspberry-pi/kvs-putmedia/src/` as needed.

3. Rebuild the package:
   ```bash
   cd raspberry-pi/kvs-putmedia
   bash ./create-package.sh
   ```

4. Deliver the new package to the board:

   **Option A — Direct copy (scp):**
   ```bash
   # On host:
   scp package.tar.gz username@<board-ip>:/opt/demo/
   # On board:
   cd /opt/demo && tar -xzf package.tar.gz --overwrite && sudo bash ./install.sh
   ```

   **Option B — OTA via /IOTCONNECT platform:**
   1. In the **Device** page, select **Firmware** on the bottom toolbar.
   2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `plitekvs` template, set version numbers (e.g., `0`, `0`), browse to `package.tar.gz`, and click **Save**.
   3. Back on the Firmware page, click the draft number under **Software Upgrades → Draft**.
   4. Click the publish icon (black square with arrow) under **Actions**.
   5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to **Devices**, select your device, and click **Update**.

   Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically. The first OTA install will take 15–20 minutes due to the SDK build.
