# KWS SageMaker Converter

This folder contains the second AWS stage in the KWS retraining flow.

Responsibilities:

- read `model-state.pt` and companion metadata from S3
- rebuild the compatible network in TensorFlow / Keras
- export `model.tflite`
- generate `labels.txt`, `package-info.json`, and `conversion-result.json`
- create a model-only `.zip` ready for `/IOTCONNECT` OTA, `file-download`, or manual installation

Use this folder when you already have trained weights and need the final runtime package.

## Prerequisites

- AWS CLI v2
- Docker Desktop
- Python on Windows with the `py` launcher
- an IAM identity that can use ECR, Step Functions, and S3
- the `/IOTCONNECT` conversion state machine ARN

See:

- [`../docs/AWS_SETUP.md`](../docs/AWS_SETUP.md)
- [`../docs/OPERATIONS.md`](../docs/OPERATIONS.md)

## Recommended Workflow

The recommended workflow is PowerShell on Windows.

Initialize tooling:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd "<repo-root>\\microchip-sama7d65-curiosity\\kws training\\sagemaker-convert"
.\setup-powershell.ps1
```

Build and push the image:

```powershell
$ConverterImageUri = .\build-and-push.ps1 `
  -AccountId "<aws-account-id>" `
  -Region "<aws-region>" `
  -RepositoryName "kws-training-converter"
```

Start conversion:

```powershell
.\start-conversion.ps1 `
  -ProcessingImageUri $ConverterImageUri `
  -InputS3Uri "s3://<models-bucket>/kws-training/weights/<training-job-name>/" `
  -OutputS3Uri "s3://<models-bucket>/kws-training/converted/<conversion-job-name>/" `
  -StateMachineArn "<conversion-state-machine-arn>"
```

## Required Input Prefix

The converter expects the input S3 prefix to contain:

- `model-state.pt`
- `labels.txt`
- `training-result.json`

If you pass the full file URI to `model-state.pt`, the helper script normalizes it to the containing prefix and automatically uses `model-state.pt` as the weight filename.

## Outputs

The conversion output prefix contains:

- `model.tflite`
- `labels.txt`
- `package-info.json`
- `conversion-result.json`
- `<name>-model.zip`

That `.zip` is a model-only deployment package for [`../../kws-demo`](../../kws-demo/).

## How The Board Uses This Stage

When the board app has:

- AWS credentials
- `KWS_TRAINING_PIPELINE_IMAGE_URI`
- `KWS_TRAINING_STATE_MACHINE_ARN`
- `KWS_TRAINING_AUTO_CONVERT_AFTER_TRAIN=1`

it can automatically launch this stage after the SageMaker training job completes.

## Notes

- `labels.txt` inside the conversion output is the canonical label order
- the final zip filename is only a convenience label and should not be treated as the authoritative label list
