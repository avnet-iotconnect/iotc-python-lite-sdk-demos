# AWS Setup

This guide describes the cloud-side setup required to reproduce the full pipeline on any AWS account.

## 1. Required AWS Resources

You need these resources before the system is fully operational:

- one S3 bucket for raw dataset uploads
- one S3 bucket for training and conversion outputs
- one SageMaker execution role for the custom training container
- one ECR repository for the training image
- one ECR repository for the conversion image
- one `/IOTCONNECT` Step Functions conversion state machine, typically named with a `conv-` prefix

If your `/IOTCONNECT` tenant already provisioned AWS resources through its CloudFormation flow, reuse those instead of creating parallel resources manually.

## 2. Local Operator Environment

The recommended workstation flow is Windows PowerShell, because both AWS helper folders include PowerShell scripts.

Install:

- AWS CLI v2
- Docker Desktop with Linux containers enabled
- Python on Windows with the `py` launcher

Verify:

```powershell
aws --version
docker version
py -3 --version
```

In each new PowerShell session, use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## 3. Use IAM, Not The Root User

Do not use the AWS root user for this workflow.

Create or use an IAM identity for the workstation that can:

- push and pull ECR images
- create and describe SageMaker training jobs
- read and write the dataset and model buckets
- start and describe Step Functions executions
- pass the SageMaker execution role

Typical permissions needed by the workstation identity:

- `ecr:*` actions required for image push and pull
- `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`
- `sagemaker:CreateTrainingJob`, `sagemaker:DescribeTrainingJob`, `sagemaker:ListTrainingJobs`
- `states:StartExecution`, `states:DescribeExecution`, `states:DescribeStateMachine`
- `iam:PassRole`
- optional `iam:GetRole` and `iam:ListRoles` for discovery and validation

Configure the CLI with either:

- `aws configure --profile <profile-name>`
- `aws configure sso --profile <profile-name>`

Then set the profile for your PowerShell session:

```powershell
$env:AWS_PROFILE = "<profile-name>"
$env:AWS_REGION = "<aws-region>"
aws sts get-caller-identity
```

## 4. SageMaker Training Execution Role

Create a SageMaker execution role for the custom trainer if you do not already have one.

The trust policy must allow SageMaker:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sagemaker.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

The permissions policy must allow:

- read access to the dataset bucket
- read and write access to the models bucket
- pull access to the training image in ECR
- CloudWatch Logs access for training output

If the same role will also be used by the conversion pipeline, add any extra S3 and ECR permissions required by the converter.

## 5. `/IOTCONNECT` Conversion Resources

The conversion stage depends on the AWS resources provisioned for `/IOTCONNECT`.

Confirm that you can identify:

- the conversion state machine ARN
- the output models bucket
- the processing role used by the conversion pipeline

The state machine often accepts an input payload like:

- processing image URI
- input S3 prefix containing `model-state.pt`
- output S3 prefix for the converted artifacts
- weights filename
- project name
- instance type and volume size

The helper script in [`../sagemaker-convert/start-conversion.ps1`](../sagemaker-convert/start-conversion.ps1) formats that input for you.

## 6. Build And Push The Training Image

Initialize tooling:

```powershell
cd "<repo-root>\\microchip-sama7d65-curiosity\\demos\\key-word-spotter\\kws training\\sagemaker-train"
.\setup-powershell.ps1
```

Build and push:

```powershell
$AccountId = "<aws-account-id>"
$Region = "<aws-region>"

$TrainerImageUri = .\build-and-push.ps1 `
  -AccountId $AccountId `
  -Region $Region `
  -RepositoryName "kws-training-trainer"
```

Record the returned image URI. It will look like:

```text
<aws-account-id>.dkr.ecr.<aws-region>.amazonaws.com/kws-training-trainer:<tag>
```

## 7. Build And Push The Conversion Image

Initialize tooling:

```powershell
cd "<repo-root>\\microchip-sama7d65-curiosity\\demos\\key-word-spotter\\kws training\\sagemaker-convert"
.\setup-powershell.ps1
```

Build and push:

```powershell
$AccountId = "<aws-account-id>"
$Region = "<aws-region>"

$ConverterImageUri = .\build-and-push.ps1 `
  -AccountId $AccountId `
  -Region $Region `
  -RepositoryName "kws-training-converter"
```

Record the returned image URI.

## 8. Validate AWS Readiness

These checks catch most setup mistakes early.

Verify the images exist:

```powershell
aws ecr describe-images `
  --repository-name kws-training-trainer `
  --region <aws-region>

aws ecr describe-images `
  --repository-name kws-training-converter `
  --region <aws-region>
```

Verify the SageMaker role exists:

```powershell
aws iam get-role --role-name <sagemaker-training-role-name>
```

Verify the conversion state machine exists:

```powershell
aws stepfunctions describe-state-machine `
  --state-machine-arn <conversion-state-machine-arn> `
  --region <aws-region>
```

## 9. Board AWS Credentials

Board-driven SageMaker training requires standard AWS credentials on the board. The app uses the normal AWS resolution chain, so any of these work:

- environment variables
- `~/.aws/credentials`
- `~/.aws/config`
- an attached role on the host platform, if available

If the board will only upload datasets and a workstation will launch training, board AWS credentials are optional.

## 10. Output Paths To Standardize

Pick stable prefixes up front so retraining runs are easy to find later.

Recommended examples:

- dataset uploads: `device-uploads/<device-id>/...`
- SageMaker output: `kws-training/output/`
- plain weights: `kws-training/weights/`
- converted packages: `kws-training/converted/`

Use the same prefixes in:

- the board environment
- the PowerShell helper invocations
- your Step Functions launch inputs
