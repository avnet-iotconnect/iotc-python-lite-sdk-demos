# Architecture

## Purpose

This system turns a Linux edge board into a keyword-data collection station and uses AWS to produce a deployable keyword spotting model package.

The design goal is to keep the board simple:

- the board captures audio
- `/IOTCONNECT` handles device identity, file support, and cloud commands
- SageMaker handles compute-heavy training and conversion
- the final artifact comes back as the same kind of model package already supported by [`../../kws-demo`](../../kws-demo/)

## End-To-End Flow

```text
Board UI
  -> capture WAV clips per label
  -> build dataset archive + manifest
  -> upload archive to S3 through /IOTCONNECT file support
  -> start SageMaker training job
  -> training writes model-state.pt + labels.txt + training-result.json
  -> board or host starts conversion pipeline
  -> Step Functions launches SageMaker Processing with converter image
  -> converter writes model.tflite + package-info.json + model zip
  -> deploy zip back to kws-demo through OTA or file-download
```

## Major Components

### Board Flask App

Files:

- [`../src/training_app.py`](../src/training_app.py)
- [`../src/iotconnect_flow.py`](../src/iotconnect_flow.py)
- [`../src/iotconnect_bridge.py`](../src/iotconnect_bridge.py)
- [`../src/templates/index.html`](../src/templates/index.html)
- [`../src/static/app.js`](../src/static/app.js)

Responsibilities:

- record clips with ALSA `arecord`
- manage label folders under `datasets/`
- create a `.tar.gz` dataset archive plus manifest JSON
- upload the archive through `/IOTCONNECT` native file support when available
- fall back to direct S3 upload when explicitly configured
- publish telemetry and receive cloud commands through `iotconnect-sdk-lite`
- submit SageMaker training jobs
- optionally watch the SageMaker job and automatically launch conversion

### `/IOTCONNECT`

Responsibilities:

- provision the device identity and certificate-based MQTT connection
- expose file-upload configuration such as bucket selection and file topic
- receive telemetry from the training app
- deliver commands such as `upload-dataset`, `start-training`, and `file-download`
- optionally manage OTA delivery of the final model package

### Telemetry Bucket

Purpose:

- stores raw dataset archives and manifest files uploaded from the board

Typical contents:

- `device-uploads/<device-id>/<yyyy>/<mm>/<dd>/kws-dataset-<timestamp>.tar.gz`
- `device-uploads/<device-id>/<yyyy>/<mm>/<dd>/kws-dataset-<timestamp>.manifest.json`

### SageMaker Training Stage

Folder:

- [`../sagemaker-train/`](../sagemaker-train/)

Purpose:

- consume the raw dataset archive
- extract labeled WAV clips
- compute the same feature shape expected by the board runtime
- train a PyTorch keyword model
- write both a plain state artifact and companion metadata to the models bucket

Outputs:

- `model-state.pt`
- `model.pt`
- `labels.txt`
- `training-result.json`
- the standard SageMaker `model.tar.gz`

### Conversion Stage

Folder:

- [`../sagemaker-convert/`](../sagemaker-convert/)

Purpose:

- rebuild the compatible network in TensorFlow / Keras
- load `model-state.pt`
- export `model.tflite`
- create `package-info.json`
- produce a ready-to-deploy model-only `.zip`

This stage is designed to work with the `/IOTCONNECT`-provisioned `conv-*` Step Functions workflow.

### Runtime Consumer

Folder:

- [`../../kws-demo/`](../../kws-demo/)

Purpose:

- run the final `.tflite` model on the board
- accept replacement model packages through OTA or `file-download`

## Runtime Modes

### Upload Modes

- `auto`
  The app prefers `/IOTCONNECT` native upload and falls back to direct S3 only if configured.
- `iotconnect`
  Force `/IOTCONNECT` native upload. Use when the device identity already exposes file support.
- `direct`
  Force direct `boto3` upload to the configured S3 bucket.

### Training Modes

- `auto`
  Prefer direct SageMaker training when the board has AWS credentials and training settings. If that is not ready but conversion-only settings are present, the app can run conversion against an already-existing `.pt` artifact.
- `direct-sagemaker`
  Upload dataset, launch the custom trainer, then optionally auto-convert on completion.
- `iotconnect-conversion`
  Skip raw dataset training and only run the `.pt` to `.tflite` conversion workflow.

## Artifact Lifecycle

| Stage | Artifact | Format | Produced By | Consumed By |
| --- | --- | --- | --- | --- |
| Board capture | dataset archive | `.tar.gz` | Flask app | trainer |
| Board capture | dataset manifest | `.json` | Flask app | trainer |
| Training | model state | `.pt` | trainer | converter |
| Training | labels | `.txt` | trainer | converter, final package |
| Training | training summary | `.json` | trainer | operators, converter context |
| Conversion | model | `.tflite` | converter | `kws-demo` |
| Conversion | package info | `.json` | converter | `kws-demo` |
| Conversion | model package | `.zip` | converter | OTA, `file-download`, manual install |

## Model Compatibility Contract

The trainer and converter are aligned to the board runtime used by [`../../kws-demo/src/kws_engine.py`](../../kws-demo/src/kws_engine.py).

Key assumptions:

- audio is `16 kHz`, mono
- clip length is `1` second by default
- MFCC window is `40 ms`
- MFCC stride is `20 ms`
- mel bin count is `40`
- DCT coefficient count is `10`
- flattened feature size is `490`

If you change the board-side feature extraction contract, you must update both AWS stages as well.

## Why Training And Conversion Are Separate

The `/IOTCONNECT`-managed AWS resources commonly provide a conversion-oriented Step Functions flow. That is a good fit for:

- converting already-trained weights
- standardizing processing
- producing package artifacts for deployment

It is not enough for raw audio retraining by itself. The custom training container fills that gap. The full pipeline is therefore:

1. board uploads dataset
2. trainer produces `model-state.pt`
3. conversion pipeline produces `model.tflite` and the deployment zip

## Automation Boundaries

The board can run in three useful operating patterns:

1. Upload only
   The board captures and uploads data through `/IOTCONNECT`, and a workstation launches training later.
2. Upload plus training
   The board also has AWS credentials and launches SageMaker jobs itself.
3. Upload plus training plus auto-convert
   The board launches training, monitors it, then automatically starts conversion and waits for the final package.

The current app supports all three patterns.
