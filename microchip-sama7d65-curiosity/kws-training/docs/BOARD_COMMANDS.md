# Board Commands

This file is a board-side command cheat sheet for the current Microchip SAMA7D65 `/IOTCONNECT` KWS setup.

Use these commands from the board serial terminal as `root`.

Important rule:

- do not run `kws-training`, `kws-demo`, and `kws-game` at the same time with the same `/IOTCONNECT` device identity

## Identity Split

This board now uses two separate `/IOTCONNECT` device identities:

- `kws-demo` uses `ZaL1`
- `kws-training` uses `mcpKWS1`

Board-side config folders:

- `/root/zal1-config`
- `/root/mcpkws1-config`

Helper start scripts:

- `/root/stop-kws-apps.sh`
- `/root/start-kws-demo-zal1.sh`
- `/root/start-kws-training-mcpkws1.sh`

These scripts now:

- stop competing `kws-training`, `kws-demo`, and `kws-game` processes first
- run in the foreground for serial-console use
- stop when you press `Ctrl+C`

This avoids duplicate MQTT client ID collisions between demo and training and avoids leaving detached processes behind while testing.

## 1. Stop All KWS Processes

Preferred command:

```bash
/root/stop-kws-apps.sh
```

Expanded form:

```bash
pkill -f 'training_app.py' || true
pkill -f 'kws_demo.py' || true
pkill -f '/root/kws-demo/app.py' || true
pkill -f 'game_app.py' || true
sleep 2
ps -ef | grep -E 'training_app.py|kws_demo.py|/root/kws-demo/app.py|game_app.py' | grep -v grep || true
```

If any process comes back immediately, it is probably being restarted by a service:

```bash
systemctl list-units --type=service | grep -Ei 'kws|demo|training'
systemctl stop <service-name>
```

## 2. Freshly Start `kws-training`

This starts only the Flask training app as `mcpKWS1` and keeps the full SageMaker plus conversion flow enabled.

The current default training profile is:

- real commands: `deal`, `double`, `hit`, `reset`, `stand`
- negative classes: `_unknown_` and `_background_noise_`
- model family: DS-CNN MFCC
- Speech Commands pretraining: enabled
- MUSAN supplemental noise: enabled from `https://www.openslr.org/resources/17/musan.tar.gz`

It first stops all other KWS apps, then runs the Flask server in the foreground.

Preferred command:

```bash
/root/start-kws-training-mcpkws1.sh
```

Expanded form:

```bash
/root/stop-kws-apps.sh
cd /root/kws-training/src
export AWS_REGION=us-east-1
export KWS_ARECORD_DEVICE=plughw:0,0
export KWS_TRAINING_PORT=8091
export KWS_IOTC_CONFIG_JSON=/root/mcpkws1-config/iotcDeviceConfig.json
export KWS_IOTC_DEVICE_CERT=/root/mcpkws1-config/device-cert.pem
export KWS_IOTC_DEVICE_KEY=/root/mcpkws1-config/device-pkey.pem
export KWS_TRAINING_OUTPUT_BUCKET=iotc-761303338807-model-1775928760254
export KWS_SAGEMAKER_ROLE_ARN=arn:aws:iam::761303338807:role/sagemaker-execution-role-761303338807
export KWS_SAGEMAKER_IMAGE_URI=761303338807.dkr.ecr.us-east-1.amazonaws.com/kws-training-trainer:20260414-215521
export KWS_TRAINING_PIPELINE_IMAGE_URI=761303338807.dkr.ecr.us-east-1.amazonaws.com/kws-training-converter:20260414-215535
export KWS_TRAINING_STATE_MACHINE_ARN=arn:aws:states:us-east-1:761303338807:stateMachine:conv-1775928760254
export KWS_TRAINING_AUTO_CONVERT_AFTER_TRAIN=1
export KWS_TRAINING_PIPELINE_OUTPUT_PREFIX=kws-training/converted
export KWS_TRAINING_DEFAULT_LABELS=deal,double,hit,reset,stand
export KWS_SAGEMAKER_TRAIN_EPOCHS=30
export KWS_SAGEMAKER_TRAIN_BATCH_SIZE=32
export KWS_SAGEMAKER_TRAIN_LEARNING_RATE=0.0007
export KWS_TRAIN_PRETRAIN_ENABLED=1
export KWS_TRAIN_PRETRAIN_REQUIRED=0
export KWS_TRAIN_PRETRAIN_SOURCE=http://download.tensorflow.org/data/speech_commands_v0.02.tar.gz
export KWS_TRAIN_PRETRAIN_EPOCHS=6
export KWS_TRAIN_PRETRAIN_MAX_SAMPLES_PER_LABEL=1800
export KWS_TRAIN_PRETRAIN_VALIDATION_SPLIT=0.1
export KWS_TRAIN_PRETRAIN_LEARNING_RATE=0.001
export KWS_TRAIN_PRETRAIN_WORDS=yes,no,up,down,left,right,on,off,stop,go
export KWS_TRAIN_MUSAN_SOURCE=https://www.openslr.org/resources/17/musan.tar.gz
export KWS_TRAIN_MUSAN_MAX_CLIPS=128
/usr/bin/python3 -u ./training_app.py
```

Open the UI at:

```text
http://<board-ip>:8091
```

Stop it with `Ctrl+C`.

## 3. Watch `kws-training`

Inspect current app state:

```bash
curl -s http://127.0.0.1:8091/api/state | python3 -m json.tool
```

## 3A. Optimize Clips Before Training

Run this only when no recording is active.

Dry-run first:

```bash
python3 /root/kws-training/scripts/optimize_dataset_clips.py \
  --dataset-root /root/kws-training/src/datasets \
  --dry-run
```

Apply the optimization in place:

```bash
python3 /root/kws-training/scripts/optimize_dataset_clips.py \
  --dataset-root /root/kws-training/src/datasets
```

What it does:

- trims leading and trailing silence from speech clips
- keeps a small pre-roll and post-roll margin
- pads clips back to the fixed one-second length
- skips `_background_noise_` by default
- backs up the original files under `optimized-backups/<timestamp>/`

Check the generated report:

```bash
find /root/kws-training/src/optimized-backups -name optimize-report.json | tail -n 1 | xargs cat
```

## 4. Start A Fresh Training Run

This triggers upload, SageMaker training, and automatic conversion.

If you do not pass a label list, the board app now defaults to:

- `deal`
- `double`
- `hit`
- `reset`
- `stand`
- `_unknown_`, if present
- `_background_noise_`, if present

```bash
curl -s -X POST http://127.0.0.1:8091/api/aws/train \
  -H 'Content-Type: application/json' \
  -d '{}' | python3 -m json.tool
```

To force the recommended five-command set explicitly:

```bash
curl -s -X POST http://127.0.0.1:8091/api/aws/train \
  -H 'Content-Type: application/json' \
  -d '{"labels":["deal","double","hit","reset","stand","_unknown_","_background_noise_"]}' | python3 -m json.tool
```

To train only selected labels:

```bash
curl -s -X POST http://127.0.0.1:8091/api/aws/train \
  -H 'Content-Type: application/json' \
  -d '{"labels":["deal","hit","stand","_unknown_","_background_noise_"]}' | python3 -m json.tool
```

## 5. Check Whether Training And Conversion Finished

Look at the last workflow fields:

```bash
curl -s http://127.0.0.1:8091/api/state | python3 -m json.tool
```

Wait until:

- `runtime.last_training_job` is populated
- `runtime.last_conversion_job` is populated
- `runtime.last_conversion_output` contains the converted package S3 URI
- `runtime.last_error` is blank

You can also grep the log for the high-signal workflow events:

```bash
grep -E 'TRAIN|CONVERT|DEPLOY|ERROR' /root/kws-training/kws-training-8091.log | tail -n 40
```

## 6. Install The Latest Converted Model Onto The Device

This uses the Flask install route and the latest package from the converted S3 prefix.

```bash
curl -s -X POST http://127.0.0.1:8091/api/models/install \
  -H 'Content-Type: application/json' \
  -d '{}' | python3 -m json.tool
```

Verify what landed in the model directory:

```bash
cat /opt/demo/models/labels.txt
cat /opt/demo/models/package-info.json
```

Current expected five-command install:

```text
_silence_
_unknown_
deal
double
hit
reset
stand
```

## 7. Stop Everything Again Before Testing

```bash
/root/stop-kws-apps.sh
```

## 8. Freshly Start `kws-demo` With The Newly Installed Model

This starts the runtime demo as `ZaL1`.

It first stops all other KWS apps, then runs the demo in the foreground.

Preferred command:

```bash
/root/start-kws-demo-zal1.sh
```

Expanded form:

```bash
/root/stop-kws-apps.sh
cd /root/kws-demo
export KWS_CONFIG_DIR=/root/zal1-config
export LD_LIBRARY_PATH=/root/kws-demo/libs
export KWS_MODEL_DIR=/opt/demo/models
export KWS_ARECORD_DEVICE=plughw:0,0
export KWS_DETECTION_THRESHOLD=0.80
export KWS_MIN_SIGNAL_RMS=0.015
export KWS_COOLDOWN_SECS=1.0
export KWS_TELEMETRY_SECS=15
/root/kws-venv/bin/python -u /root/kws-demo/kws_demo.py
```

Stop it with `Ctrl+C`.

Verify the installed labels again:

```bash
cat /opt/demo/models/labels.txt
```

Verify the installed package metadata:

```bash
cat /opt/demo/models/package-info.json
```

## 9. Watch The New Model

You will see the live output directly in the serial terminal.

Healthy silence should look like:

```text
top=_silence_ score=0.000 detected=False
```

Real detections should look like:

```text
top=deal score=...
top=hit score=...
top=stand score=...
```

## 10. One Full End-To-End Flow

If you want the exact order in one place:

1. run `Stop All KWS Processes`
2. run `Freshly Start kws-training`
3. use the Flask UI to record more clips if needed
4. run `Start A Fresh Training Run`
5. wait until `runtime.last_conversion_output` is populated
6. run `Install The Latest Converted Model Onto The Device`
7. run `Stop Everything Again Before Testing`
8. run `Freshly Start kws-demo With The Newly Installed Model`
9. run `Watch The New Model`
