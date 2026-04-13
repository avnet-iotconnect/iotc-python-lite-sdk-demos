# Operations

This guide covers normal day-to-day use after setup is complete.

## 1. Capture New Clips

Open the board UI:

```text
http://<board-ip>:<port>
```

For each command:

1. type a new label or select an existing label
2. press `Start Recording`
3. speak the command once
4. press `Stop And Save Clip`
5. repeat until you have enough examples

Recommendations:

- capture clips from multiple speakers when possible
- record several tones, speaking speeds, and microphone distances
- keep labels stable once you start training against them
- create `_background_noise_` clips if you want explicit background examples

## 2. Upload A Dataset Without Training

Use the UI or the HTTP API when you only want to push data to S3.

UI:

- press the upload action in the page

HTTP API:

```bash
curl -X POST http://<board-ip>:<port>/api/aws/upload \
  -H 'Content-Type: application/json' \
  -d '{"labels":["command-one","command-two"]}'
```

If `labels` is omitted, the app uploads all known labels.

## 3. Run End-To-End Training From The Board

This requires:

- board AWS credentials
- a configured SageMaker training role
- a trainer image URI
- a converter image URI if auto-conversion is enabled
- a configured conversion state machine

UI:

- press `Start Training`

HTTP API:

```bash
curl -X POST http://<board-ip>:<port>/api/aws/train \
  -H 'Content-Type: application/json' \
  -d '{"labels":["command-one","command-two"]}'
```

The board will:

1. create the dataset archive and manifest
2. upload them to the telemetry bucket
3. submit a SageMaker training job
4. poll the training job until it completes
5. start the conversion workflow if auto-conversion is enabled
6. poll the conversion workflow until the final package is ready

## 4. Manual Workstation-Driven Training

This path is useful when:

- you do not want AWS credentials on the board
- you want to rerun training with different hyperparameters
- you want tighter operator control over job submission

### Build The Trainer Image

```powershell
cd "<repo-root>\\microchip-sama7d65-curiosity\\kws training\\sagemaker-train"
.\setup-powershell.ps1

$TrainerImageUri = .\build-and-push.ps1 `
  -AccountId "<aws-account-id>" `
  -Region "<aws-region>"
```

### Submit Training

```powershell
.\submit-job.ps1 `
  -ImageUri $TrainerImageUri `
  -RoleArn "arn:aws:iam::<aws-account-id>:role/<sagemaker-training-role>" `
  -DatasetS3Uri "s3://<telemetry-bucket>/<dataset-archive-key>" `
  -ManifestS3Uri "s3://<telemetry-bucket>/<manifest-key>" `
  -OutputBucket "<models-bucket>" `
  -WantedWords "command-one,command-two"
```

The returned training output gives you the `model-state.pt` location needed for conversion.

## 5. Manual Workstation-Driven Conversion

### Build The Converter Image

```powershell
cd "<repo-root>\\microchip-sama7d65-curiosity\\kws training\\sagemaker-convert"
.\setup-powershell.ps1

$ConverterImageUri = .\build-and-push.ps1 `
  -AccountId "<aws-account-id>" `
  -Region "<aws-region>"
```

### Start Conversion

Point the conversion at the S3 prefix containing:

- `model-state.pt`
- `labels.txt`
- `training-result.json`

```powershell
.\start-conversion.ps1 `
  -ProcessingImageUri $ConverterImageUri `
  -InputS3Uri "s3://<models-bucket>/kws-training/weights/<training-job-name>/" `
  -OutputS3Uri "s3://<models-bucket>/kws-training/converted/<conversion-job-name>/" `
  -StateMachineArn "<conversion-state-machine-arn>"
```

## 6. Monitor Jobs

### Training Job

```powershell
aws sagemaker describe-training-job `
  --training-job-name <training-job-name> `
  --region <aws-region> `
  --query "{Status:TrainingJobStatus,Secondary:SecondaryStatus,Failure:FailureReason}" `
  --output table
```

### Conversion Execution

```powershell
aws stepfunctions describe-execution `
  --execution-arn <execution-arn> `
  --region <aws-region> `
  --query "{Status:status,Output:output}" `
  --output table
```

### Board App State

```bash
curl http://<board-ip>:<port>/api/state
```

Important fields:

- `upload.status`
- `training.status`
- `training.mode`
- `training.in_progress`
- `runtime.last_training_job`
- `runtime.last_conversion_job`
- `runtime.last_conversion_output`

## 7. Retrieve The Final Model Package

The final package is written to the configured conversion output prefix and has a model-only layout.

Download it locally:

```powershell
aws s3 cp `
  "s3://<models-bucket>/kws-training/converted/<conversion-job-name>/<model-package>.zip" `
  ".\\<model-package>.zip"
```

## 8. Deploy The Package To `kws-demo`

You have three practical options.

### OTA Through `/IOTCONNECT`

Use the platform’s firmware or file-delivery flow to publish the model-only `.zip`.

### Command-Based Delivery

Send the `file-download` command to the target device with the package URL.

### Manual Install On The Board

Copy the package to the board and extract it into the `kws-demo` app directory:

```bash
python3 -m zipfile -e <model-package>.zip .
bash ./install.sh
```

The package format is documented in [`../../kws-demo/packages/README.md`](../../kws-demo/packages/README.md).

## 9. Retraining After Adding More Clips

When you add more data:

1. keep the same label names
2. upload or train again from the board
3. compare the new `training-result.json` with previous runs
4. deploy the new package only if the model quality improved

Do not assume a model is good just because the AWS pipeline completed successfully. Review:

- dataset size by label
- validation accuracy
- false positives and missed detections on the board

## 10. Common Failure Modes

### Upload Works But Training Does Not

Likely causes:

- the board has `/IOTCONNECT` file support but no AWS credentials
- `KWS_SAGEMAKER_ROLE_ARN` is missing
- `KWS_SAGEMAKER_IMAGE_URI` is missing
- `KWS_TRAINING_OUTPUT_BUCKET` is missing

### Training Works But Conversion Does Not Start

Likely causes:

- `KWS_TRAINING_PIPELINE_IMAGE_URI` is missing
- `KWS_TRAINING_STATE_MACHINE_ARN` is missing and auto-discovery failed
- the conversion state machine lacks permission to access the model artifacts

### Conversion Completes But The Runtime Model Fails

Likely causes:

- labels do not match model output order
- the trainer and converter no longer match the board feature extraction contract
- the model package was installed into the wrong application directory

### Training Quality Is Poor

Typical fixes:

- add more clips per label
- add more speaker variation
- remove mislabeled clips
- rebalance labels with very different clip counts
- verify the microphone path and capture quality on the board
