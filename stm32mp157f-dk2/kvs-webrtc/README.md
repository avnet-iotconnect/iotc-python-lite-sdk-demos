# KVS WebRTC Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the STM32MP157F-DK2 to the AWS Kinesis Video Streams (KVS) WebRTC live video streaming demo.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the STM32MP157F-DK2](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/stm32mp157f-dk2/README.md) before proceeding.

## 1. Introduction

This demo streams live video from a USB camera through the STM32MP157F-DK2 to a browser or other WebRTC viewer via AWS Kinesis Video Streams (KVS) WebRTC. The device acts as a WebRTC MASTER: it connects to the KVS signaling channel provided by /IOTCONNECT and streams video to any VIEWER that connects.

Unlike the KVS PutMedia demo, WebRTC is a peer-to-peer protocol — the video is delivered directly between the device and the viewer with very low latency. No pre-built KVS C++ SDK libraries need to be installed; all WebRTC signaling and media encoding is handled in Python by `aiortc` and `boto3`.

The default capture resolution is 640×480 at 15 fps to stay within the Cortex-A7's CPU budget alongside the software encoding performed by aiortc.

## 2. Set Up Hardware and Template

1. Plug a USB camera into a USB port on the STM32MP157F-DK2.

> [!TIP]
> Verify the camera is detected by running `ls /dev/video*` on the device. The app automatically identifies USB cameras by inspecting the hardware path of each video device, so it picks the correct one even if the onboard camera interface is also present.

> [!IMPORTANT]
> This demo requires the `webrtc` template (available [here](webrtc-template.json)). The device **must be created in /IOTCONNECT with the `webrtc` template** — the AWS backend provisions a KVS WebRTC signaling channel for `webrtc` devices and a KVS stream for `putmedia` devices, and these cannot be switched after device creation. If your device was created with `plitedemo` or `putmedia`, create a new device using `webrtc`.

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/stm32mp157f-dk2/kvs-webrtc/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

> [!NOTE]
> Warning messages in the console during the installation script are expected and can be ignored. The `aiortc` and `av` packages may take several minutes to install on this board.

### Run

```bash
python3 app.py
```

## 4. Using the Demo

Once the application is running and connected to /IOTCONNECT:

- **Telemetry**: Sends a random integer and the current streaming status (true/false) every 10 seconds.
- **Auto-start**: If KVS is configured with auto-start in /IOTCONNECT, the video capture pipeline and WebRTC signaling begin automatically 3 seconds after connecting.
- **Manual control**: Video streaming can be started/stopped via /IOTCONNECT commands from the device's **Video Streaming** tab. A **Start** button appears when streaming is off; a **Stop** button appears when streaming is active.
- **Viewing the stream**: Open the device's **Video Streaming** tab in the /IOTCONNECT portal and click the live view button to open the WebRTC viewer. The viewer connects to the KVS signaling channel and receives the stream directly from the device.

### Camera Configuration

The default camera settings in `app.py` are:
- Resolution: 640×480
- Framerate: 15 fps

These can be adjusted by modifying the `camera_options` dictionary in `app.py`. Reduce the resolution or framerate if the board's CPU cannot keep up with both capture and WebRTC encoding simultaneously.

## 5. Customize and Rebuild (Optional)

To modify the demo files before deploying:

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `stm32mp157f-dk2/kvs-webrtc/src/` as needed.

3. Rebuild the package:
   ```bash
   cd stm32mp157f-dk2/kvs-webrtc
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
2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `webrtc` template, set version numbers (e.g., `0`, `0`), browse to `package.tar.gz`, and click **Save**.
3. Back on the Firmware page, click the draft number under **Software Upgrades → Draft**.
4. Click the publish icon (black square with arrow) under **Actions**.
5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to **Devices**, select your device, and click **Update**.

> [!NOTE]
> Warning messages in the console during the installation script are expected and can be ignored.

Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically.
