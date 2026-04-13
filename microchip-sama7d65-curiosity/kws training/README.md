# KWS Training Studio

This folder contains a complete retraining pipeline for board-hosted keyword spotting:

1. capture new voice-command clips on the target board with a Flask UI
2. upload dataset archives through `/IOTCONNECT` file support
3. train a PyTorch keyword model in Amazon SageMaker
4. convert the trained weights into a board-ready TensorFlow Lite package
5. deploy the generated model package back to the runtime used by [`../kws-demo`](../kws-demo/)

The implementation is intentionally split into two AWS stages:

- `sagemaker-train/` handles raw dataset training and produces `model-state.pt`
- `sagemaker-convert/` handles `.pt` to `.tflite` conversion and packaging

That split matches the common `/IOTCONNECT` pattern where the provisioned `conv-*` Step Functions pipeline is a conversion workflow, not a raw-audio training workflow.

## Contents

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md): end-to-end system design, artifacts, and runtime modes
- [`docs/DIAGRAMS.md`](./docs/DIAGRAMS.md): Mermaid diagrams for architecture, setup, training, conversion, and deployment
- [`docs/AWS_SETUP.md`](./docs/AWS_SETUP.md): AWS, IAM, ECR, SageMaker, and Step Functions setup
- [`docs/BOARD_SETUP.md`](./docs/BOARD_SETUP.md): board deployment, `/IOTCONNECT` provisioning, and startup
- [`docs/OPERATIONS.md`](./docs/OPERATIONS.md): daily usage, retraining flow, monitoring, and deployment
- [`docs/REFERENCE.md`](./docs/REFERENCE.md): environment variables, HTTP API, template telemetry, and commands
- [`kws-training-template.json`](./kws-training-template.json): `/IOTCONNECT` template for the training device
- [`sagemaker-train/`](./sagemaker-train/): custom SageMaker training container and PowerShell helpers
- [`sagemaker-convert/`](./sagemaker-convert/): custom conversion container and Step Functions launcher
- [`src/`](./src/): Flask app, static UI, `/IOTCONNECT` bridge, and board-side capture logic

## Quick Start

1. Provision the AWS side.
   Create or identify a telemetry bucket, a models bucket, a SageMaker training execution role, and the `/IOTCONNECT` Step Functions conversion state machine.
2. Build the AWS images.
   Use the PowerShell scripts in `sagemaker-train/` and `sagemaker-convert/` to build and push both images to ECR.
3. Provision the device in `/IOTCONNECT`.
   Import [`kws-training-template.json`](./kws-training-template.json), create a device, and place the generated device config and certificates on the board.
4. Install the board app.
   Copy this folder to the board, run [`src/install.sh`](./src/install.sh), and start [`src/training_app.py`](./src/training_app.py).
5. Decide where training jobs will be submitted from.
   Upload-only mode works with `/IOTCONNECT` credentials alone. Full board-driven training requires AWS credentials on the board.
6. Capture data.
   Open the Flask UI, create or select labels, and record clips one utterance at a time.
7. Start training.
   The app uploads the dataset, submits a SageMaker training job, waits for completion, and can automatically start conversion when configured.
8. Deploy the generated model package.
   Publish the resulting `.zip` package through `/IOTCONNECT` OTA or install it manually in [`../kws-demo`](../kws-demo/).

## What The Board App Does

- records `16 kHz` mono WAV clips with `arecord`
- stores clips under `src/datasets/<label>/`
- packages the dataset into a `.tar.gz` archive plus a manifest JSON
- prefers `/IOTCONNECT` native file upload when the device identity exposes file support
- falls back to direct `boto3` S3 upload when explicitly configured
- publishes training telemetry through `iotconnect-sdk-lite`
- accepts `/IOTCONNECT` commands for upload, training, restart, and package download
- starts direct SageMaker training jobs when AWS credentials and a trainer image are configured
- automatically starts the conversion pipeline after successful training when a converter image and Step Functions state machine are configured

## Repository Layout

```text
kws training/
  README.md
  docs/
    ARCHITECTURE.md
    AWS_SETUP.md
    BOARD_SETUP.md
    OPERATIONS.md
    REFERENCE.md
  kws-training-template.json
  sagemaker-train/
  sagemaker-convert/
  src/
    training_app.py
    iotconnect_flow.py
    iotconnect_bridge.py
    install.sh
    static/
    templates/
    datasets/
    exports/
```

`datasets/` and `exports/` are created automatically on first run.

## Output Package Format

The final conversion output is a model-only `.zip` compatible with the existing package rules in [`../kws-demo/packages/README.md`](../kws-demo/packages/README.md). The minimum contents are:

```text
install.sh
models/model.tflite
models/labels.txt
models/package-info.json
```

That package can be delivered through `/IOTCONNECT` OTA, the `file-download` command, or manual extraction on the board.

## Recommended Setup Order

1. Read [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
2. Review [`docs/DIAGRAMS.md`](./docs/DIAGRAMS.md)
3. Complete [`docs/AWS_SETUP.md`](./docs/AWS_SETUP.md)
4. Complete [`docs/BOARD_SETUP.md`](./docs/BOARD_SETUP.md)
5. Use [`docs/OPERATIONS.md`](./docs/OPERATIONS.md) for capture, retraining, and deployment
6. Use [`docs/REFERENCE.md`](./docs/REFERENCE.md) when you need exact variable names, API routes, or template details

## Security Notes

- Do not use the AWS root user for CLI, ECR, SageMaker, or board automation.
- Use least-privileged IAM identities for:
  - the local workstation that builds images and launches jobs
  - the board, if the board itself will submit SageMaker jobs
  - the SageMaker execution role used by the training container
- Store board AWS credentials in the standard AWS shared credentials format and rotate them when needed.
- Treat the board certificate, private key, and `/IOTCONNECT` device config as device secrets.
