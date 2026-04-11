# Packages

This folder contains ready-to-use `.zip` archives for the Microchip SAMA7D65 KWS demo.

Use `.zip` for new packages. The packaged app now extracts `.zip` directly for `/IOTCONNECT` OTA and `file-download`. It also still accepts legacy `.tar.gz` archives for backward compatibility.

Manual extraction on the board:

```bash
python3 -m zipfile -e <package>.zip .
```

## Package Types

Full app replacement package:

- includes `app.py`, `kws_engine.py`, `install.sh`, and bundled model assets
- use this when you want to replace the whole KWS demo
- package: `kws-demo-package.zip`

Model-only replacement package:

- includes `install.sh`, `models/model.tflite`, `models/labels.txt`, and `models/package-info.json`
- use this when the app code stays the same and only the model changes
- these are safe for `/IOTCONNECT` OTA or the `file-download` command when `install.sh` avoids mandatory native-package builds on the target

Minimum model-only contents:

```text
install.sh
models/model.tflite
models/labels.txt
models/package-info.json
```

`package-info.json` is used by the runtime to publish:

- `model_package`: the package that installed the active model
- `model_sha256`: SHA-256 of the active `model.tflite`

`labels.txt` must contain one label per line in the exact output order of the model. For the Arm recipe used here, that is normally:

```text
_silence_
_unknown_
<wanted_word_1>
<wanted_word_2>
...
```

## Included Archives

- `kws-demo-package.zip`: full KWS app package
- `model-ds-cnn-small-int8.zip`: current default model package
- `model-ds-cnn-small-fp32.zip`: floating-point DS-CNN Small
- `model-ds-cnn-medium-int8.zip`: larger int8 DS-CNN Medium
- `model-ds-cnn-medium-fp32.zip`: larger fp32 DS-CNN Medium
- `model-cnn-small-int8.zip`: smaller alternative CNN model

The runtime supports `fp32`, `int8`, and `uint8` TFLite models. It does not support `int16` models, so no `int16` packages are included here.

## Rebuild

To regenerate this folder:

```bash
python ./packages/build_packages.py
```

That script refreshes the archives and writes `manifest.json` with sizes and hashes.

The bundled `install.sh` is intentionally conservative for OTA use on Yocto boards: it does not force-upgrade `numpy`, and it treats `numpy` and `tflite-runtime` installs as best-effort so a missing compiler toolchain does not abort the package install.

How to tell that a model update succeeded:

- the board log prints `OTA successful. Restarting the application...`
- telemetry counters restart from `0`
- `model_package` changes to the uploaded archive name
- `model_sha256` changes to the new model hash
