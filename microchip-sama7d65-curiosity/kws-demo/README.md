# Keyword Spotting Demo

Adds a USB microphone based keyword spotter to the Microchip SAMA7D65-Curiosity Kit and publishes inference results to /IOTCONNECT.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Microchip SAMA7D65-Curiosity Kit](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/microchip-sama7d65-curiosity/README.md) before proceeding.

## 1. Introduction

This demo replaces the random-number telemetry loop with a lightweight speech-command classifier. The application captures one-second audio clips from a USB microphone, computes MFCC features locally, runs a TensorFlow Lite keyword spotting model on the board CPU, and pushes the top prediction to /IOTCONNECT.

The bundled model is Arm's quantized `DS-CNN Small` Speech Commands model. The stock labels are:

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

For the current custom retraining flow used with [`../kws training/`](../kws%20training/), the board can instead run a board-trained DS-CNN package from `/opt/demo/models`. The current recommended custom label set is:

- `_silence_`
- `_unknown_`
- `deal`
- `double`
- `hit`
- `reset`
- `stand`

## 2. Set Up Hardware and Template

1. Plug a USB microphone into one of the board's USB host ports.
2. Confirm the microphone is visible to ALSA:

```bash
arecord -l
```

3. Create your device in /IOTCONNECT with [kws-template.json](./kws-template.json).

Notes:

- The template `code` is `sama7d6Kws`. That shortened value is intentional because `/IOTCONNECT` template codes are limited to `10` characters.
- The template exposes telemetry for the latest inference, accepted detections, threshold, active heartbeat interval, and audio device.
- The template commands are `listen-start`, `listen-stop`, `set-threshold`, `set-interval`, and `file-download`.

## 3. Telemetry Behavior

The app now sends telemetry in two cases:

- immediately on an accepted keyword event
- on a heartbeat every `60` seconds by default

The heartbeat can be changed at runtime with the `set-interval` command. Example:

```text
set-interval 30
```

Relevant telemetry fields:

- `kws_label`: top class from the latest inference
- `kws_confidence`: score for the latest top class
- `kws_detected`: `true` only on the event packet for an accepted detection
- `last_detected_word`: last accepted keyword event
- `detection_count`: accepted keyword events since app start
- `telemetry_interval`: current heartbeat interval in seconds
- `audio_device`: ALSA capture device used by the app
- `model_name`: installed runtime model filename, typically `model.tflite`
- `model_package`: package that installed the current model, for example `model-ds-cnn-small-fp32.zip`
- `model_sha256`: SHA-256 of the active `model.tflite`

To confirm an OTA model swap worked, check for all of these:

- `OTA successful. Restarting the application...` in the board log
- startup telemetry with `inference_count: 0` and `detection_count: 0`
- updated `model_package` and `model_sha256` values in telemetry

## 4. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/microchip-sama7d65-curiosity/kws-demo/packages/kws-demo-package.zip
python3 -m zipfile -e kws-demo-package.zip .
bash ./install.sh
```

The installer:

- verifies `iotconnect-sdk-lite` and `requests` are available
- checks whether `numpy` is already importable before attempting a best-effort install
- checks whether `tflite-runtime` is already importable before attempting a best-effort install
- copies the bundled model assets into `/opt/demo/models`
- keeps both `model.tflite` and `ds_cnn_s_quantized.tflite` available for compatibility

> [!NOTE]
> On minimal Yocto images, `numpy` or `tflite-runtime` may not have compatible wheels. The installer now warns instead of failing the OTA, but inference still requires both a working `numpy` and a TensorFlow Lite interpreter on the target.

### Run

```bash
python3 app.py
```

By default, the demo starts listening immediately. Use `KWS_AUTOSTART=0` if you want the app to start idle and only listen after a cloud command.

## 5. Commands

- `listen-start`: starts continuous keyword capture and inference
- `listen-stop`: stops audio capture but keeps the app connected
- `set-threshold`: changes the detection threshold at runtime, for example `0.85`
- `set-interval`: changes the heartbeat interval in seconds, for example `60`
- `file-download`: downloads and installs a replacement `.zip` package, then restarts the app

## 6. Environment Overrides

You can tune the demo without editing `app.py`:

```bash
export KWS_AUTOSTART=1
export KWS_DETECTION_THRESHOLD=0.80
export KWS_COOLDOWN_SECS=2.0
export KWS_TELEMETRY_SECS=60
export KWS_ARECORD_DEVICE=plughw:1,0
export KWS_MODEL_DIR=/opt/demo/models
export KWS_MODEL_FILE=model.tflite
export KWS_LABELS_FILE=labels.txt
export KWS_CONFIG_DIR=/root
```

`KWS_CONFIG_DIR` lets you point the demo at a specific `/IOTCONNECT` device identity directory containing:

- `iotcDeviceConfig.json`
- `device-cert.pem`
- `device-pkey.pem`

Notes:

- `KWS_AUTOSTART=0` starts the demo idle.
- `KWS_DETECTION_THRESHOLD` must be between `0.0` and `1.0`.
- `KWS_COOLDOWN_SECS` suppresses duplicate detections from back-to-back clips.
- `KWS_TELEMETRY_SECS` sets the default heartbeat interval before any cloud command changes it.
- `KWS_ARECORD_DEVICE` lets you pin the app to a specific USB mic if the default ALSA selection is wrong.
- `KWS_MODEL_DIR`, `KWS_MODEL_FILE`, and `KWS_LABELS_FILE` let you swap in a different model package later.

### Current Board Helper Script Flow

When using the paired training workflow in [`../kws training/`](../kws%20training/), the preferred board command is:

```bash
/root/start-kws-demo-zal1.sh
```

That script:

- stops competing `kws-training`, `kws-demo`, and `kws-game` processes first
- uses `ZaL1` as the `/IOTCONNECT` identity
- points `KWS_MODEL_DIR` at `/opt/demo/models`
- runs the demo in the foreground for serial-console use

After installing a new converted model, verify the active package and labels with:

```bash
cat /opt/demo/models/labels.txt
cat /opt/demo/models/package-info.json
```

## 7. Training New Commands

Host-side training assets live in [training/](./training/).

That folder includes:

- a dataset layout reference
- a DS-CNN Small training command script
- an export script that emits `model.tflite` and `labels.txt`
- an optional model-only `.zip` generator for OTA or `file-download`

Start with [training/README.md](./training/README.md).

## 8. Replacement Package Format

Use `.zip`.

The current OTA and `file-download` flow expects a zip archive that extracts and then runs `install.sh`. A replacement model-only package should contain:

```text
install.sh
models/model.tflite
models/labels.txt
models/package-info.json
```

A full app replacement package contains the app files plus the model assets:

```text
app.py
kws_engine.py
install.sh
models/model.tflite
models/labels.txt
```

Notes:

- `labels.txt` must contain one label per line in model output order.
- `package-info.json` is strongly recommended because the runtime uses it to report `model_package`.
- Only the `.tflite` model file is needed for inference, but for OTA packaging it should be wrapped in a `.zip` with `install.sh`.
- The runtime supports `fp32`, `int8`, and `uint8` TFLite models. `int16` packages are not supported by this demo.

## 9. Ready-Made Packages

Prebuilt archives live in [packages/](./packages/). The main ones are:

- `kws-demo-package.zip`: full app package
- `model-ds-cnn-small-int8.zip`: current default model package
- `model-ds-cnn-small-fp32.zip`: floating-point DS-CNN Small
- `model-ds-cnn-medium-int8.zip`: larger DS-CNN Medium
- `model-ds-cnn-medium-fp32.zip`: larger floating-point DS-CNN Medium
- `model-cnn-small-int8.zip`: smaller CNN alternative

Those model-only packages let you try other official Arm keyword-spotting models without changing the app code.

## 10. Rebuild Packages

To rebuild the full app package:

```bash
bash ./create-package.sh
```

That refreshes:

- `package.zip`
- `packages/kws-demo-package.zip`
- `../../common/package.zip`

To regenerate the stock model packages in `packages/`:

```bash
python ./packages/build_packages.py
```

## 11. Deliver a New Package

**Option A - Direct copy (scp):**

```bash
# On host:
scp ./packages/kws-demo-package.zip root@<board-ip>:/opt/demo/
# On board:
cd /opt/demo && python3 -m zipfile -e kws-demo-package.zip . && bash ./install.sh
```

For a model-only update, replace `kws-demo-package.zip` with one of the model packages from `packages/`.

**Option B - OTA via /IOTCONNECT platform:**

1. In the **Device** page, select **Firmware** on the bottom toolbar.
2. Create a new firmware if needed, using the `sama7d6Kws` template.
3. Upload one of the `.zip` files from [packages/](./packages/).
4. Publish the firmware draft.
5. Create an OTA update targeting your device.

The running app will receive the package, decompress it, execute `install.sh`, and restart automatically.

If the board image lacks a compiler toolchain, avoid OTA packages whose `install.sh` force-upgrades heavy native packages such as `numpy`. Those installs tend to fail during metadata build on Yocto.

## 12. Model Sources

The bundled and optional stock models come from Arm's archived ML Zoo keyword spotting assets:

- [DS-CNN Small](https://github.com/Arm-Examples/ML-zoo/tree/master/models/keyword_spotting/ds_cnn_small/model_package_tf)
- [DS-CNN Medium](https://github.com/Arm-Examples/ML-zoo/tree/master/models/keyword_spotting/ds_cnn_medium/model_package_tf)
- [CNN Small](https://github.com/Arm-Examples/ML-zoo/tree/master/models/keyword_spotting/cnn_small/model_package_tf)
