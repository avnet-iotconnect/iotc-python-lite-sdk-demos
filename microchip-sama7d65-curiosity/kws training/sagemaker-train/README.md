# KWS SageMaker Trainer

This folder contains the first AWS stage in the KWS retraining flow.

Responsibilities:

- read a board-produced dataset archive from S3
- unpack labeled WAV clips and the manifest
- extract features compatible with the board runtime
- train a PyTorch keyword model
- write `model-state.pt`, `model.pt`, `labels.txt`, and `training-result.json`

Use this folder when you need to turn raw audio data into the `.pt` artifact consumed by the conversion pipeline.

## Prerequisites

- AWS CLI v2
- Docker Desktop
- Python on Windows with the `py` launcher
- an IAM identity that can use ECR, SageMaker, and S3
- a SageMaker execution role for the training job

See:

- [`../docs/AWS_SETUP.md`](../docs/AWS_SETUP.md)
- [`../docs/OPERATIONS.md`](../docs/OPERATIONS.md)

## Recommended Workflow

The recommended workflow is PowerShell on Windows.

Initialize tooling:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd "<repo-root>\\microchip-sama7d65-curiosity\\kws training\\sagemaker-train"
.\setup-powershell.ps1
```

Build and push the image:

```powershell
$TrainerImageUri = .\build-and-push.ps1 `
  -AccountId "<aws-account-id>" `
  -Region "<aws-region>" `
  -RepositoryName "kws-training-trainer"
```

Submit a training job:

```powershell
.\submit-job.ps1 `
  -ImageUri $TrainerImageUri `
  -RoleArn "arn:aws:iam::<aws-account-id>:role/<sagemaker-training-role>" `
  -DatasetS3Uri "s3://<telemetry-bucket>/<dataset-archive-key>" `
  -ManifestS3Uri "s3://<telemetry-bucket>/<manifest-key>" `
  -OutputBucket "<models-bucket>" `
  -WantedWords "command-one,command-two"
```

## Outputs

The trainer writes:

- SageMaker model output under the configured `output` prefix
- `model-state.pt` under the configured `weights` prefix
- `model.pt` under the configured `weights` prefix
- `labels.txt` under the configured `weights` prefix
- `training-result.json` under the configured `weights` prefix

Use `model-state.pt` as the input to the conversion stage.

## How The Board Uses This Stage

When the board app has:

- AWS credentials
- `KWS_SAGEMAKER_ROLE_ARN`
- `KWS_SAGEMAKER_IMAGE_URI`
- `KWS_TRAINING_OUTPUT_BUCKET`

it can launch this training stage directly from the Flask UI or the `/api/aws/train` route.

## Notes

- `labels.txt` is the canonical output order for the trained model
- if `WantedWords` is omitted, the trainer uses the label set from the uploaded dataset manifest
- if you change the feature contract in the board runtime, you must keep this folder aligned with it
