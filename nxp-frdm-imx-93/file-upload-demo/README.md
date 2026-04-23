# File Upload Demo

Upgrades the /IOTCONNECT Starter Demo on the NXP FRDM-IMX93 to a media capture and file upload demo.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the NXP FRDM-IMX93](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/nxp-frdm-imx-93/README.md) before proceeding.

## 1. Introduction

This demo captures still pictures and fixed-length video clips from a USB camera, stores them locally on the board, and uploads the completed media files to the device's S3-backed /IOTCONNECT file-support bucket through `iotconnect-sdk-lite`.

The app runs in two capture modes:

- single-frame JPEG capture for on-demand pictures
- rolling MP4 clip recording through GStreamer `splitmuxsink`

Completed pictures are uploaded as `.jpg` files. Completed video clips are ZIP-wrapped immediately before upload and published as `.mp4.zip` artifacts.

## 2. Set Up Hardware and Template

1. Plug a USB camera into a USB port on the NXP FRDM-IMX93.

> [!TIP]
> Verify the camera is detected by running `ls /dev/video*` on the device. The app automatically identifies USB cameras by inspecting the hardware path of each video device.

> [!IMPORTANT]
> This demo requires the `file-upload` template (available [here](file-upload-template.json)). Create the device in /IOTCONNECT with that template so file support and the custom commands are available from the start.

The template exposes:

- telemetry attributes: `recording`, `pending_uploads`, `uploaded_clips`, `upload_failures`, `last_clip`
- commands: `capture-picture`, `record-start`, `record-stop`, `file-download`

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget -O package.tar.gz https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-93/file-upload-demo/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

The installer:

- upgrades to `iotconnect-sdk-lite[aws-s3]`
- installs `requests`
- places the bundled `x264` runtime and plugin under `/opt/video-upload-libs`
- verifies `x264enc`, `mp4mux`, and `splitmuxsink`

### Run

```bash
python3 app.py
```

The demo connects to /IOTCONNECT and starts idle by default so you can choose between picture capture and video recording. Set `VIDEO_AUTOSTART=1` if you want the clip recorder to start automatically at launch.

## 4. Using the Demo

Once the application is running and connected to /IOTCONNECT:

- `capture-picture` captures one JPEG picture and uploads it to S3. The clip recorder must be stopped first.
- `record-start` starts the MP4 clip recorder if it is not already running.
- `record-stop` stops the recorder and uploads the finalized tail clip.
- `file-download` downloads and installs a replacement package, then restarts the app.

The demo also maps /IOTCONNECT video stream control messages (`ct 112` and `ct 113`) to the same start and stop behavior as `record-start` and `record-stop`.

### Telemetry

The app sends telemetry every 10 seconds with:

- `recording`: whether the recorder process is currently running
- `pending_uploads`: local media files waiting to be uploaded
- `uploaded_clips`: number of successfully uploaded media files since boot
- `upload_failures`: upload attempts that failed since boot
- `last_clip`: last uploaded relative S3 path for either a picture or a clip

Uploaded files are published through the file-upload topic, so they appear under /IOTCONNECT **Telemetry Files**.

### Default Capture Settings

The default camera settings in `app.py` are:

- Resolution: 1280x720
- Framerate: 30 fps
- Clip length: 30 seconds
- Local media directory: `/opt/demo/video-clips`

### Environment Overrides

You can tune the app without editing `app.py`:

```bash
export VIDEO_CLIP_LENGTH_SECS=15
export VIDEO_UPLOAD_SCAN_SECS=3
export VIDEO_UPLOAD_MIN_FILE_AGE_SECS=2
export VIDEO_UPLOAD_DIR=/opt/demo/video-clips
export VIDEO_DELETE_AFTER_UPLOAD=1
export VIDEO_AUTOSTART=0
```

Notes:

- `VIDEO_CLIP_LENGTH_SECS` controls the fixed MP4 segment duration in seconds. The default is `30`.
- `VIDEO_UPLOAD_SCAN_SECS` controls how often the background uploader scans the local media directory for finished files to upload. Lower values reduce upload latency but wake the uploader more often. The default is `5`.
- `VIDEO_UPLOAD_MIN_FILE_AGE_SECS` sets the minimum age a file must reach before the uploader treats it as stable enough to upload. This helps avoid racing a file that is still being finalized. The default is `3`.
- `VIDEO_UPLOAD_DIR` selects the local directory used for captured pictures, completed MP4 clips, and pending uploads. The default is `/opt/demo/video-clips`.
- `VIDEO_DELETE_AFTER_UPLOAD=1` deletes local pictures and MP4 clips after a successful upload. Setting it to `0` retains the files locally, but because the uploader watches the same directory for pending files, retained files will be uploaded again on later scans unless you move them elsewhere.
- `VIDEO_AUTOSTART=1` starts MP4 recording automatically when the app launches. The default `0` leaves the demo idle until you send `record-start` or `capture-picture`.

## 5. Customize and Rebuild (Optional)

To modify the demo files before deploying:

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `nxp-frdm-imx-93/file-upload-demo/src/` as needed.

3. Rebuild the package:
   ```bash
   cd nxp-frdm-imx-93/file-upload-demo
   bash ./create-package.sh
   ```

`create-package.sh` prefers fresh shared libraries from `VIDEO_UPLOAD_LIBS_DIR` when it is set. Otherwise it falls back to `~/kvs-libs-imx93/`, and if that directory is not present it reuses the bundled libraries already embedded in the current `package.tar.gz`.

## 6. Deliver the New Package

**Option A - Direct copy (scp):**

```bash
# On host:
scp package.tar.gz root@<board-ip>:/opt/demo/
# On board:
cd /opt/demo && tar -xzf package.tar.gz --overwrite && bash ./install.sh
```

**Option B - OTA via /IOTCONNECT platform:**

1. In the **Device** page, select **Firmware** on the bottom toolbar.
2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `file-upload` template, set version numbers (for example `0`, `0`), browse to `package.tar.gz`, and click **Save**.
3. Back on the Firmware page, click the draft number under **Software Upgrades -> Draft**.
4. Click the publish icon (black square with arrow) under **Actions**.
5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to **Devices**, select your device, and click **Update**.

Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically.
