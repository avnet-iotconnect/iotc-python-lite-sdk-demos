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

The current recommended training path is intentionally narrower than the full label inventory some older demos used:

- default command set: `deal`, `double`, `hit`, `reset`, `stand`
- default model: DS-CNN over MFCC features
- default pretraining: TensorFlow Speech Commands v0.02
- default board-side supplemental noise source: `https://www.openslr.org/resources/17/musan.tar.gz`

That split matches the common `/IOTCONNECT` pattern where the provisioned `conv-*` Step Functions pipeline is a conversion workflow, not a raw-audio training workflow.

## Contents

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md): end-to-end system design, artifacts, and runtime modes
- [`docs/DIAGRAMS.md`](./docs/DIAGRAMS.md): Mermaid diagrams for architecture, setup, training, conversion, and deployment
- [`docs/AWS_SETUP.md`](./docs/AWS_SETUP.md): AWS, IAM, ECR, SageMaker, and Step Functions setup
- [`docs/BOARD_SETUP.md`](./docs/BOARD_SETUP.md): board deployment, `/IOTCONNECT` provisioning, and startup
- [`docs/BOARD_COMMANDS.md`](./docs/BOARD_COMMANDS.md): exact serial-terminal commands for stopping apps, starting training, installing the latest model, and testing `kws-demo`
- [`docs/OPERATIONS.md`](./docs/OPERATIONS.md): daily usage, retraining flow, monitoring, and deployment
- [`docs/REFERENCE.md`](./docs/REFERENCE.md): environment variables, HTTP API, template telemetry, and commands
- [`scripts/`](./scripts/): board helper scripts plus dataset cleanup and clip-optimization tools
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
   Open the Flask UI, use the `Collection Plan` panel to identify the weakest command folders plus `_unknown_` and `_background_noise_`, then record clips one utterance at a time.
7. Start training.
   The app uploads the dataset, submits a SageMaker training job, waits for completion, and can automatically start conversion when configured. By default, board-triggered training now targets `deal`, `double`, `hit`, `reset`, and `stand` plus `_unknown_` and `_background_noise_`.
8. Deploy the generated model package.
   Use the Flask `Install Converted Model` panel to browse converted packages in S3 and install one onto the board, or publish the resulting `.zip` package through `/IOTCONNECT` OTA.

## What The Board App Does

- records `16 kHz` mono WAV clips with `arecord`
- stores clips under `src/datasets/<label>/`
- computes a guided collection plan so operators can balance command clips and negative data before retraining
- packages the dataset into a `.tar.gz` archive plus a manifest JSON
- prefers `/IOTCONNECT` native file upload when the device identity exposes file support
- falls back to direct `boto3` S3 upload when explicitly configured
- publishes training telemetry through `iotconnect-sdk-lite`
- accepts `/IOTCONNECT` commands for upload, training, restart, and package download
- starts direct SageMaker training jobs when AWS credentials and a trainer image are configured
- defaults new training runs to the more distinct five-word command set unless explicit labels are supplied
- uses a DS-CNN MFCC keyword model instead of the older tiny MLP baseline
- can pretrain the DS-CNN backbone on Speech Commands before fine-tuning on board data
- can merge MUSAN clips into the `_background_noise_` pool during board-driven training
- automatically starts the conversion pipeline after successful training when a converter image and Step Functions state machine are configured
- lists converted model packages from the models bucket and can install a selected package onto `/opt/demo/models`

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
  scripts/
    clean_dataset.py
    optimize_dataset_clips.py
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
