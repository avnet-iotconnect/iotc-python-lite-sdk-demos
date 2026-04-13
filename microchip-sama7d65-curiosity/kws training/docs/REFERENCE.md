# Reference

## Environment Variables

### Core Web App

| Variable | Default | Purpose |
| --- | --- | --- |
| `KWS_TRAINING_HOST` | `0.0.0.0` | Flask bind host |
| `KWS_TRAINING_PORT` | `8090` | Flask bind port |
| `KWS_TRAINING_DEBUG` | `0` | Enable Flask debug mode when set to `1`, `true`, or `yes` |
| `KWS_TRAINING_DATASET_ROOT` | `<src>/datasets` | Dataset folder root |
| `KWS_TRAINING_EXPORT_ROOT` | `<src>/exports` | Archive and manifest export root |
| `KWS_TRAINING_SAMPLE_RATE` | `16000` | Capture sample rate |
| `KWS_TRAINING_CHANNELS` | `1` | Capture channel count |
| `KWS_TRAINING_CLIP_SECONDS` | `1` | Default clip duration |
| `KWS_ARECORD_DEVICE` | empty | ALSA device passed to `arecord` |

### Upload Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `KWS_TRAINING_UPLOAD_MODE` | `auto` | `auto`, `iotconnect`, or `direct` |
| `KWS_TRAINING_DATA_BUCKET` | empty | Direct-upload S3 bucket |
| `KWS_TRAINING_DATA_PREFIX` | `kws-training/datasets` | Direct-upload S3 prefix |

### `/IOTCONNECT` Integration

| Variable | Default | Purpose |
| --- | --- | --- |
| `KWS_IOTC_TELEMETRY_SECS` | `60` | Periodic telemetry interval |
| `KWS_IOTC_CONFIG_JSON` | `/root/iotcDeviceConfig.json` | Device config JSON path |
| `KWS_IOTC_DEVICE_CERT` | `/root/device-cert.pem` | Device certificate path |
| `KWS_IOTC_DEVICE_KEY` | `/root/device-pkey.pem` | Device private key path |
| `KWS_IOTC_CA_CERT` | empty | Optional CA bundle path |
| `KWS_IOTC_DISCOVERY_URL` | empty | Optional discovery URL override |
| `KWS_IOTC_BUCKET_NAME` | empty | Force a specific upload bucket |
| `KWS_IOTC_FS_URL` | empty | Override file-system credentials URL |
| `KWS_IOTC_FS_BUCKETS_JSON` | empty | Override bucket selection JSON |
| `KWS_IOTC_FILE_TOPIC` | empty | Override file publish topic |
| `KWS_IOTC_MQTT_HOST` | empty | Override MQTT host |
| `KWS_IOTC_MQTT_PORT` | empty | Override MQTT port |
| `KWS_IOTC_MQTT_USERNAME` | empty | Override MQTT username |
| `KWS_IOTC_MQTT_CLIENT_ID` | empty | Override MQTT client ID |
| `KWS_IOTC_DEVICE_ID` | empty | Override device ID used for file upload |

### SageMaker Training

| Variable | Default | Purpose |
| --- | --- | --- |
| `KWS_TRAINING_OUTPUT_BUCKET` | empty | Bucket for training outputs |
| `KWS_TRAINING_OUTPUT_PREFIX` | `kws-training/output` | SageMaker output prefix |
| `KWS_SAGEMAKER_WEIGHTS_PREFIX` | `kws-training/weights` | Plain artifact prefix |
| `KWS_SAGEMAKER_ROLE_ARN` | empty | SageMaker training execution role |
| `KWS_SAGEMAKER_IMAGE_URI` | empty | Trainer image URI |
| `KWS_SAGEMAKER_INSTANCE_TYPE` | `ml.m5.xlarge` | Training instance type |
| `KWS_SAGEMAKER_INSTANCE_COUNT` | `1` | Training instance count |
| `KWS_SAGEMAKER_MAX_RUNTIME_SECS` | `14400` | Max runtime, minimum enforced is `3600` |
| `KWS_SAGEMAKER_TRAIN_EPOCHS` | `20` | Epoch count |
| `KWS_SAGEMAKER_TRAIN_BATCH_SIZE` | `16` | Batch size |
| `KWS_SAGEMAKER_TRAIN_LEARNING_RATE` | `0.001` | Learning rate |

### Conversion Pipeline

| Variable | Default | Purpose |
| --- | --- | --- |
| `KWS_TRAINING_PIPELINE_MODE` | `auto` | `auto` or `iotconnect` |
| `KWS_TRAINING_STATE_MACHINE_ARN` | empty | Step Functions state machine ARN |
| `KWS_TRAINING_STATE_MACHINE_PREFIX` | `conv-` | Prefix used for state machine auto-discovery |
| `KWS_TRAINING_PROJECT_NAME` | `kws-training` | Project name passed to the converter |
| `KWS_TRAINING_PIPELINE_IMAGE_URI` | empty | Converter image URI |
| `KWS_TRAINING_PIPELINE_INSTANCE_TYPE` | `ml.m5.xlarge` | Processing instance type |
| `KWS_TRAINING_PIPELINE_VOLUME_GB` | `30` | Processing volume size |
| `KWS_TRAINING_PIPELINE_OUTPUT_PREFIX` | `kws-training/converted` | Default conversion output prefix |
| `KWS_TRAINING_WEIGHTS_S3_URI` | empty | Existing weights URI for conversion-only runs |
| `KWS_TRAINING_WEIGHTS_NAME` | empty | Weight file name when input URI is a prefix |
| `KWS_TRAINING_PIPELINE_OUTPUT_S3_URI` | empty | Explicit output prefix override |
| `KWS_TRAINING_AUTO_CONVERT_AFTER_TRAIN` | `1` | Enable automatic conversion after training |
| `KWS_TRAINING_POLL_SECS` | `15` | Poll interval for training and conversion monitors |

### Standard AWS Configuration

The app also honors the normal AWS SDK resolution chain. Common options are:

- `AWS_REGION`
- `AWS_PROFILE`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `~/.aws/credentials`
- `~/.aws/config`

## HTTP API

### `GET /`

Returns the Flask UI.

### `GET /api/state`

Returns a JSON snapshot containing:

- label inventory
- upload readiness
- `/IOTCONNECT` status
- training and conversion status
- recent events and runtime metadata

### `POST /api/capture/start`

Body:

```json
{
  "label": "command-name"
}
```

Starts recording for the given label.

### `POST /api/capture/stop`

Stops the active recording and saves the WAV clip.

### `POST /api/aws/upload`

Body:

```json
{
  "labels": ["command-one", "command-two"]
}
```

Creates and uploads a dataset archive for the selected labels. If `labels` is omitted, all labels are included.

### `POST /api/aws/train`

Body:

```json
{
  "labels": ["command-one", "command-two"]
}
```

Creates and uploads the dataset archive, starts the training workflow, and returns the initial training state.

## `/IOTCONNECT` Template Telemetry

Defined in [`../kws-training-template.json`](../kws-training-template.json):

- `sdk_version`
- `audio_device`
- `upload_mode`
- `upload_ready`
- `upload_status`
- `iotc_file_topic`
- `iotc_bucket`
- `label_count`
- `clip_count`
- `recording`
- `current_label`
- `last_capture_at`
- `capture_clip_seconds`
- `last_archive_name`
- `last_archive_s3_uri`
- `last_manifest_s3_uri`
- `last_training_job`
- `last_training_output`
- `last_conversion_job`
- `last_conversion_output`
- `sagemaker_ready`
- `last_error`

## `/IOTCONNECT` Template Commands

Defined in [`../kws-training-template.json`](../kws-training-template.json):

- `refresh-state`
- `set-upload-mode`
- `set-audio-device`
- `set-clip-seconds`
- `upload-dataset`
- `start-training`
- `restart-app`
- `file-download`

## Dataset Layout

The board stores clips under:

```text
src/datasets/<label>/
```

Each label folder contains WAV files recorded from the UI.

The exported dataset archive contains those label folders plus a manifest JSON describing:

- selected labels
- clip counts per label
- capture settings
- wanted words for training

## Final Package Layout

The converter produces a model-only package shaped for [`../../kws-demo`](../../kws-demo/):

```text
install.sh
models/model.tflite
models/labels.txt
models/package-info.json
```

The canonical label order is `models/labels.txt`. Use that file instead of inferring the label set from the zip filename.
