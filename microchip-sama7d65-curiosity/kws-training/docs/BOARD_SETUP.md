# Board Setup

This guide covers everything needed on the target board.

## 1. Prerequisites

You need:

- a Linux board supported by the rest of this repository
- a working microphone recognized by ALSA
- network access to `/IOTCONNECT` and AWS
- device credentials from `/IOTCONNECT`

Confirm audio capture works:

```bash
arecord -l
```

If `arecord` is missing, install the package that provides ALSA utilities for your distribution.

## 2. Import The `/IOTCONNECT` Template

Import [`../kws-training-template.json`](../kws-training-template.json) into `/IOTCONNECT` and create a device from it.

That template enables:

- file support
- telemetry fields for capture, upload, training, and conversion status
- cloud commands for upload, training, restart, and package download

After the device is created, place these files on the board:

- `iotcDeviceConfig.json`
- device certificate PEM
- device private key PEM

Store them in stable paths, for example:

```text
/etc/iotconnect/iotcDeviceConfig.json
/etc/iotconnect/device-cert.pem
/etc/iotconnect/device-key.pem
```

## 3. Copy The Application To The Board

Copy the full `kws-training/` folder to a stable location on the board. Example:

```text
/opt/kws-training
```

The app expects to run from the `src/` directory:

```text
/opt/kws-training/src
```

## 4. Install Board Dependencies

From the board:

```bash
cd /opt/kws-training/src
bash ./install.sh
```

The installer checks:

- Python package availability
- Flask and AWS SDK dependencies
- `arecord` availability

If automatic package installation fails, the app can still run as long as the required packages are already present in the interpreter you plan to use.

## 5. Optional: Add AWS Credentials To The Board

This step is required only if the board itself should submit SageMaker training jobs and launch the conversion pipeline.

Create the AWS shared credentials files:

```text
/root/.aws/credentials
/root/.aws/config
```

Example:

```ini
; /root/.aws/credentials
[default]
aws_access_key_id = <access-key-id>
aws_secret_access_key = <secret-access-key>
```

```ini
; /root/.aws/config
[default]
region = <aws-region>
output = json
```

Use an IAM user or role with least-privileged access. Do not place root credentials on the board.

If you are using a non-root service account, place the same files in that user’s home directory instead.

## 6. Configure The Runtime Environment

At minimum, set the board-specific paths and audio device:

```bash
export KWS_IOTC_CONFIG_JSON=/etc/iotconnect/iotcDeviceConfig.json
export KWS_IOTC_DEVICE_CERT=/etc/iotconnect/device-cert.pem
export KWS_IOTC_DEVICE_KEY=/etc/iotconnect/device-key.pem
export KWS_ARECORD_DEVICE=plughw:0,0
export KWS_TRAINING_PORT=8090
```

For full board-driven training and auto-conversion, also set:

```bash
export AWS_REGION=<aws-region>
export KWS_TRAINING_OUTPUT_BUCKET=<models-bucket>
export KWS_SAGEMAKER_ROLE_ARN=arn:aws:iam::<aws-account-id>:role/<sagemaker-training-role>
export KWS_SAGEMAKER_IMAGE_URI=<trainer-image-uri>
export KWS_TRAINING_PIPELINE_IMAGE_URI=<converter-image-uri>
export KWS_TRAINING_STATE_MACHINE_ARN=<conversion-state-machine-arn>
export KWS_TRAINING_AUTO_CONVERT_AFTER_TRAIN=1
```

Optional but useful:

```bash
export KWS_TRAINING_UPLOAD_MODE=auto
export KWS_TRAINING_DATA_PREFIX=device-uploads
export KWS_TRAINING_OUTPUT_PREFIX=kws-training/output
export KWS_SAGEMAKER_WEIGHTS_PREFIX=kws-training/weights
export KWS_TRAINING_PIPELINE_OUTPUT_PREFIX=kws-training/converted
export KWS_IOTC_TELEMETRY_SECS=60
```

Use [`REFERENCE.md`](./REFERENCE.md) for the full variable list.

## 7. Start The Flask App

Run:

```bash
cd /opt/kws-training/src
/usr/bin/python3 ./training_app.py
```

Then open:

```text
http://<board-ip>:8090
```

If you need a different interface or port:

```bash
export KWS_TRAINING_HOST=0.0.0.0
export KWS_TRAINING_PORT=8090
```

## 8. Verify Health

Check the JSON state endpoint:

```bash
curl http://127.0.0.1:8090/api/state
```

Things to confirm:

- the audio device is correct
- `/IOTCONNECT` is connected
- upload mode is what you expect
- `training.ready` is `true` if the board should submit SageMaker jobs
- conversion is configured if auto-conversion is enabled

## 9. Optional: Run As A Service

If your distribution uses `systemd`, create a unit like this:

```ini
[Unit]
Description=KWS Training Flask App
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/kws-training/src
ExecStart=/usr/bin/python3 /opt/kws-training/src/training_app.py
Restart=always
RestartSec=5
Environment=KWS_IOTC_CONFIG_JSON=/etc/iotconnect/iotcDeviceConfig.json
Environment=KWS_IOTC_DEVICE_CERT=/etc/iotconnect/device-cert.pem
Environment=KWS_IOTC_DEVICE_KEY=/etc/iotconnect/device-key.pem
Environment=KWS_ARECORD_DEVICE=plughw:0,0
Environment=KWS_TRAINING_PORT=8090
Environment=AWS_REGION=<aws-region>
Environment=KWS_TRAINING_OUTPUT_BUCKET=<models-bucket>
Environment=KWS_SAGEMAKER_ROLE_ARN=arn:aws:iam::<aws-account-id>:role/<sagemaker-training-role>
Environment=KWS_SAGEMAKER_IMAGE_URI=<trainer-image-uri>
Environment=KWS_TRAINING_PIPELINE_IMAGE_URI=<converter-image-uri>
Environment=KWS_TRAINING_STATE_MACHINE_ARN=<conversion-state-machine-arn>
Environment=KWS_TRAINING_AUTO_CONVERT_AFTER_TRAIN=1

[Install]
WantedBy=multi-user.target
```

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kws-training
sudo systemctl start kws-training
sudo systemctl status kws-training
```

## 10. When Board AWS Credentials Are Not Present

The board can still be useful without AWS credentials.

In that mode:

- capture and upload still work through `/IOTCONNECT`
- dataset archives still land in the telemetry bucket
- a workstation can submit training and conversion later with the PowerShell helpers

That is a valid deployment model when you do not want AWS credentials stored on the board.
