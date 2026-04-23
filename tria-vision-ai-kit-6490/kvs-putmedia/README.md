# KVS PutMedia Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the Tria Vision AI-KIT 6490 to the AWS Kinesis Video Streams (KVS) PutMedia video streaming demo.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Tria Vision AI-KIT 6490](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/tria-vision-ai-kit-6490/README.md) before proceeding.

## 1. Introduction

This demo streams live video from a USB camera through the Tria Vision AI-KIT 6490 to AWS Kinesis Video Streams (KVS), accessible via the /IOTCONNECT platform. The KVS Producer SDK libraries are pre-built and bundled in the package — no on-device compilation is required.

The QCS6490 SoC includes a Qualcomm msm_vidc hardware H264 encoder that is accessible via the standard V4L2 API (`v4l2h264enc`). The USB camera is captured in MJPG format at 1280×720 to stay within USB 2.0 bandwidth limits, then decoded in software and re-encoded to H264 by the on-chip hardware encoder. The default resolution is 1280×720 at 30 fps.

## 2. Set Up Hardware and Template

1. Plug a USB camera into a USB-A port on the Tria Vision AI-KIT 6490.

> [!TIP]
> Verify the camera is detected by running `ls /dev/video*` on the device. The QCS6490 exposes several non-USB video nodes (`/dev/video0`, `/dev/video1` for the Qualcomm camera subsystem and `/dev/video32`, `/dev/video33` for the hardware codec). The app automatically identifies the USB camera by inspecting the hardware path of each video device in sysfs.

> [!IMPORTANT]
> This demo requires the `plitekvs` template (available [here](plitekvs-template.json)). The device must be created in /IOTCONNECT with the `plitekvs` template and the correct stream resource (Video Stream for a PutMedia stream or WebRTC for a WebRTC stream) must be selected during the device creation process. The AWS backend provisions a KVS WebRTC signaling channel for WebRTC devices and a KVS stream for PutMedia devices, and these cannot be switched after device creation. If your device was created with a different template, create a new device using `plitekvs` and select the appropriate stream resource.

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget -O package.tar.gz https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/tria-vision-ai-kit-6490/kvs-putmedia/package.tar.gz
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
- Resolution: 1280×720
- Framerate: 30 fps

These can be adjusted by modifying the `camera_options` dictionary in `app.py`.

## 5. Customize and Rebuild (Optional)

To modify the demo files before deploying, or to rebuild the package with a newer version of the KVS Producer SDK:

### Modify Source Files

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `tria-vision-ai-kit-6490/kvs-putmedia/src/` as needed.

3. To rebuild with the existing pre-built libraries, run:
   ```bash
   cd tria-vision-ai-kit-6490/kvs-putmedia
   bash ./create-package.sh
   ```

### Rebuild KVS Producer SDK (Advanced)

If you need to pick up a newer version of the KVS Producer SDK, cross-compile it on a Linux host using Docker:

**Prerequisites:** Docker must be installed on your host machine.

**Step 1:** Cross-compile the KVS Producer SDK for aarch64:
```bash
bash ~/kvs-build-qcs6490.sh
```
This places the resulting `.so` library files in `~/kvs-libs-qcs6490/`. The build takes several minutes.

> [!NOTE]
> The QCS6490 uses the same aarch64 target as other boards in this repo. The `kvs-build-qcs6490.sh` script uses Docker with a Debian Bookworm cross-compilation toolchain targeting `aarch64-linux-gnu`. No bundled software encoder libraries are needed — the board's hardware encoder (`v4l2h264enc`) is used instead.

**Step 2:** Rebuild the package (bundles the new libraries alongside the source files):
```bash
cd tria-vision-ai-kit-6490/kvs-putmedia
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
2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `putmedia` template, set version numbers (e.g., `0`, `0`), browse to `package.tar.gz`, and click **Save**.
3. Back on the Firmware page, click the draft number under **Software Upgrades → Draft**.
4. Click the publish icon (black square with arrow) under **Actions**.
5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to **Devices**, select your device, and click **Update**.

> [!NOTE]
> Warning messages in the console during the installation script are expected and can be ignored.

Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically.
