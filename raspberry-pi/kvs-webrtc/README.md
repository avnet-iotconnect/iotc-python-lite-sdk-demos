# KVS WebRTC Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the Raspberry Pi (4 or 5) to the AWS Kinesis Video Streams (KVS) WebRTC live video streaming demo.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Raspberry Pi](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/raspberry-pi/README.md) before proceeding.

## 1. Introduction

This demo streams live video from a USB camera through the Raspberry Pi to a browser or other WebRTC viewer via AWS Kinesis Video Streams (KVS) WebRTC. The device acts as a WebRTC MASTER: it connects to the KVS signaling channel provided by /IOTCONNECT and streams video to any VIEWER that connects.

Unlike the KVS PutMedia demo, WebRTC is a peer-to-peer protocol — the video is delivered directly between the device and the viewer with very low latency. No C++ SDK build is needed; all WebRTC signaling and media encoding is handled in Python by `aiortc` and `boto3`. PyPI provides native aarch64 wheels for all dependencies (`aiortc`, `av`/PyAV, `websockets`, `boto3`, `cffi`), so installation is a straightforward `pip install` — the main workaround needed is for Ubuntu Server 24.04's PEP 668 "externally managed environment" restriction on `pip`.

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
wget -O package.tar.gz https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/raspberry-pi/kvs-webrtc/package.tar.gz
tar -xzf package.tar.gz --overwrite
sudo bash ./install.sh
```

> [!NOTE]
> The install downloads several Python packages and GStreamer plugins. Warning messages in the console are expected and can be ignored.

> [!IMPORTANT]
> If `install.sh` stops with **`Cannot uninstall cryptography … no RECORD file was found`**, the image's `cryptography`
> package was installed via `apt` without pip metadata, so pip can't replace it. Install a pip-tracked copy over it, then
> re-run `install.sh`:
> ```bash
> sudo python3 -m pip install --break-system-packages --ignore-installed --no-deps cryptography
> sudo bash ./install.sh
> ```
> If a **different** package raises the same *"no RECORD file"* error, repeat the one-liner with that package name instead.

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
- Framerate: 30 fps

These can be adjusted by modifying the `camera_options` dictionary in `app.py`.

## 5. Customize and Rebuild (Optional)

To modify the demo files before deploying:

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `raspberry-pi/kvs-webrtc/src/` as needed.

3. Rebuild the package:
   ```bash
   cd raspberry-pi/kvs-webrtc
   bash ./create-package.sh
   ```

### Deliver the New Package

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

> [!NOTE]
> Warning messages in the console during the installation script are expected and can be ignored.

Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically.
