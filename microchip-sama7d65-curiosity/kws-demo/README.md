# Keyword Spotting Demo

Adds a USB microphone based keyword spotter to the Microchip SAMA7D65-Curiosity Kit and publishes inference results to /IOTCONNECT.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Microchip SAMA7D65-Curiosity Kit](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/microchip-sama7d65-curiosity/README.md) before proceeding.

## 1. Introduction

This demo replaces the random-number telemetry loop with a lightweight speech-command classifier. The application captures one-second audio clips from a USB microphone, computes MFCC features locally, runs a TensorFlow Lite keyword spotting model on the board CPU, and pushes the top prediction to /IOTCONNECT.

The bundled model is Arm's quantized `DS-CNN Small` Speech Commands model. It recognizes these labels:

- `_silence_`
- `_unknown_`
- `yes`
- `no`
- `up`
- `down`
- `left`
- `right`
- `on`
- `off`
- `stop`
- `go`

## 2. Set Up Hardware and Template

1. Plug a USB microphone into one of the board's USB host ports.
2. Confirm the microphone is visible to ALSA:

```bash
arecord -l
```

3. Create your device in /IOTCONNECT with the [KWS template](kws-template.json).

The template exposes:

- telemetry attributes for the latest inference, detection counters, threshold, and audio device
- commands: `listen-start`, `listen-stop`, `set-threshold`, `file-download`

## 3. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/microchip-sama7d65-curiosity/kws-demo/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

The installer:

- upgrades `iotconnect-sdk-lite`
- installs `requests` and `numpy`
- attempts to install `tflite-runtime`
- places the bundled model assets under `/opt/demo/models`

> [!NOTE]
> If `tflite-runtime` is not available for the Python ABI in your Yocto image, the install still completes, but the app will need a compatible TensorFlow Lite interpreter before inference can run.

### Run

```bash
python3 app.py
```

By default, the demo starts listening immediately. Use `KWS_AUTOSTART=0` if you want the app to start idle and only listen after a cloud command.

## 4. Using the Demo

Once the application is running and connected to /IOTCONNECT:

- `listen-start` starts continuous keyword capture and inference
- `listen-stop` stops audio capture but keeps the app connected
- `set-threshold` changes the detection threshold at runtime, for example `0.85`
- `file-download` downloads and installs a replacement package, then restarts the app

Telemetry fields of interest:

- `kws_label`: current top label from the latest inference
- `kws_confidence`: score for the top label
- `kws_detected`: `true` only when a non-silence/non-unknown label clears the threshold and cooldown gate
- `last_detected_word`: last accepted keyword event
- `detection_count`: accepted keyword events since app start
- `audio_device`: ALSA capture device used by the app

## 5. Environment Overrides

You can tune the demo without editing `app.py`:

```bash
export KWS_AUTOSTART=1
export KWS_DETECTION_THRESHOLD=0.80
export KWS_COOLDOWN_SECS=2.0
export KWS_TELEMETRY_SECS=2
export KWS_ARECORD_DEVICE=plughw:1,0
export KWS_MODEL_DIR=/opt/demo/models
```

Notes:

- `KWS_AUTOSTART=0` starts the demo idle.
- `KWS_DETECTION_THRESHOLD` must be between `0.0` and `1.0`.
- `KWS_COOLDOWN_SECS` suppresses duplicate detections from back-to-back clips.
- `KWS_ARECORD_DEVICE` lets you pin the app to a specific USB mic if the default ALSA selection is wrong.
- `KWS_MODEL_DIR` lets you swap in a retrained model later as long as the app can still find `labels.txt`.

## 6. Customize and Rebuild

To modify the demo files before deploying:

1. Clone the repository to your host machine:

```bash
git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
```

2. Edit files in `microchip-sama7d65-curiosity/kws-demo/src/` as needed.
3. Rebuild the package:

```bash
cd microchip-sama7d65-curiosity/kws-demo
bash ./create-package.sh
```

## 7. Deliver the New Package

**Option A - Direct copy (scp):**

```bash
# On host:
scp package.tar.gz root@<board-ip>:/opt/demo/
# On board:
cd /opt/demo && tar -xzf package.tar.gz --overwrite && bash ./install.sh
```

**Option B - OTA via /IOTCONNECT platform:**

1. In the **Device** page, select **Firmware** on the bottom toolbar.
2. Create a new firmware if needed, using the `sama7d65KwsDemo` template.
3. Publish the firmware draft.
4. Create an OTA update targeting your device.

Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart automatically.

## 8. Model Source

The bundled model originates from Arm's archived ML Zoo keyword spotting assets:

- [model page](https://github.com/Arm-Examples/ML-zoo/tree/master/models/keyword_spotting/ds_cnn_small/model_package_tf/model_archive/TFLite/tflite_int8)
- [labels source](https://github.com/ARM-software/ML-KWS-for-MCU/tree/master/Pretrained_models)
