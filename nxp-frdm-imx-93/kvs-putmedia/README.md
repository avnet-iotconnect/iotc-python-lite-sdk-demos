# Picture And Video Upload Demo

This branch repurposes the original `nxp-frdm-imx-93/kvs-putmedia` demo into a clip recorder that:

- captures single JPEG pictures from the USB camera on demand
- captures USB camera video on the NXP FRDM-IMX93
- writes fixed-length MP4 clips locally with GStreamer
- uploads completed pictures and ZIP-wrapped video clips to the device's S3 file-support bucket through `iotconnect-sdk-lite`
- publishes the file-upload message so the media appears in /IOTCONNECT

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the NXP FRDM-IMX93](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/nxp-frdm-imx-93/README.md) before proceeding.

## 1. Hardware and Template

1. Plug a USB camera into a USB port on the NXP FRDM-IMX93.
2. Verify the camera is present with `ls /dev/video*`.
3. Create the device in /IOTCONNECT using [video-upload-template.json](video-upload-template.json).

The template enables file support and exposes:

- telemetry attributes: `recording`, `pending_uploads`, `uploaded_clips`, `upload_failures`, `last_clip`
- commands: `capture-picture`, `record-start`, `record-stop`, `file-download`

## 2. How It Works

The app uses `gst-launch-1.0` in two modes:

- single-frame JPEG capture for still pictures
- `splitmuxsink` for rolling MP4 clips

Default behavior:

- clip length: 30 seconds
- resolution: 1280x720
- frame rate: 30 fps
- local clip directory: `/opt/demo/video-clips`
- video upload path in S3: `device-uploads/<client-id>/clips/YYYY/MM/DD/<clip-file>.mp4.zip`
- picture upload path in S3: `device-uploads/<client-id>/pictures/YYYY/MM/DD/<picture-file>.jpg`

Completed media files are uploaded in a background worker. MP4 clips are ZIP-archived immediately before upload so the downloaded file preserves the original bytes across the current /IOTCONNECT download path. After a successful upload, the local file is deleted by default.
If the recorder crashes, the app leaves recording stopped and prints recent GStreamer stderr so you can inspect the real failure before sending `record-start` again.

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/frdm93-video_upload/nxp-frdm-imx-93/kvs-putmedia/package.tar.gz
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

If the device template includes file support, the demo connects to /IOTCONNECT and starts idle by default so you can choose between picture capture and video recording. Set `VIDEO_AUTOSTART=1` if you want the MP4 recorder to start automatically at launch.
The demo also maps `/IOTCONNECT` video stream control messages (`ct 112` / `ct 113`) to the same start and stop behavior.

## 4. Commands and Telemetry

Commands:

- `capture-picture`: captures one JPEG picture and uploads it to S3. This requires the MP4 recorder to be stopped.
- `record-start`: starts the MP4 clip recorder if it is not already running
- `record-stop`: stops the recorder and uploads the last finalized clip
- `file-download`: downloads and installs a replacement package, then restarts the app

Telemetry sent every 10 seconds:

- `recording`: recorder process running or not
- `pending_uploads`: media files waiting to be uploaded
- `uploaded_clips`: number of successfully uploaded media files since boot
- `upload_failures`: upload attempts that failed since boot
- `last_clip`: last uploaded relative S3 path for either a picture or a clip

Uploaded files are published through the file-upload topic, so they should appear in /IOTCONNECT Telemetry Files.

## 5. Environment Overrides

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

- `VIDEO_CLIP_LENGTH_SECS` controls the fixed MP4 segment duration.
- `VIDEO_DELETE_AFTER_UPLOAD=0` keeps local MP4 clips and JPEG captures after upload. Temporary ZIP archives used for clip uploads are always cleaned up after each attempt.
- `VIDEO_AUTOSTART=1` starts MP4 recording automatically when the app launches.

## 6. Rebuild the Package

To rebuild the package on a host machine:

```bash
cd nxp-frdm-imx-93/kvs-putmedia
bash ./create-package.sh
```

`create-package.sh` prefers fresh shared libraries from `~/kvs-libs-imx93/`. If those are not available, it reuses the bundled libraries already present in the existing `package.tar.gz`.

## 7. OTA Delivery

You can still deliver this package through the /IOTCONNECT OTA flow. Upload the generated `package.tar.gz` as firmware, target the device created from `video-upload-template.json`, and the running app will download, install, and restart itself.
