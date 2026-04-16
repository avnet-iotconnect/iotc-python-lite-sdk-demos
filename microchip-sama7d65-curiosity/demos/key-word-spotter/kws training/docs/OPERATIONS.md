# Operations

This guide covers normal day-to-day use after setup is complete.

## Recommended Training Profile

The default board-driven training flow is now tuned for a smaller, more reliable command set:

- real commands: `deal`, `double`, `hit`, `reset`, `stand`
- negative classes: `_unknown_` and `_background_noise_`
- model family: DS-CNN over MFCC features
- pretraining source: Speech Commands v0.02
- board-side supplemental noise source: `https://www.openslr.org/resources/17/musan.tar.gz`

Older labels such as `lower`, `raise`, and `safe` can remain archived in the dataset history, but the default `Start Training` path should no longer include them unless you explicitly pass them in the API request.

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
- use the `Collection Plan` panel in the Flask UI to identify the weakest folders first
- create `_unknown_` clips with non-command words and short phrases
- create `_background_noise_` clips with room tone, HVAC, keyboard noise, and other non-speech ambient sound
- use the `Retire` button in the command-folder list when you want to archive an obsolete label without deleting its clips

### Collection Plan Guidance

The UI now ranks what to capture next.

- command folders below the minimum floor should be fixed first
- `_unknown_` clips help the model reject unrelated spoken words
- `_background_noise_` clips help the model reject silence and ambient sound

Recommended starting targets:

- each command label: `40-60` clips
- `_unknown_`: `30-50` clips
- `_background_noise_`: `20-40` clips

### 15-Minute Strengthening Pass

Use this checklist when the model is over-triggering, confusing command words, or failing to reject silence and unrelated speech.

| Step | Label | Time | Clips To Add | What To Record | Done |
| --- | --- | --- | --- | --- | --- |
| 1 | `_background_noise_` | 4 minutes | 20 | 5 quiet room clips, 5 HVAC or fan clips, 5 keyboard or mouse clips, 5 chair movement or table noise clips. Stay silent during every clip. | [ ] |
| 2 | `_unknown_` | 6 minutes | 30 | One non-command utterance per clip. Use words and short phrases like `hello`, `thanks`, `cancel`, `maybe`, `what time`, `good morning`, `play music`. Do not say any real command words. | [ ] |
| 3 | weakest real command | 1-2 minutes | 5-10 | Add clips to the weakest command folder first. Vary tone, speed, volume, and mic distance. | [ ] |
| 4 | second weakest command | 1-2 minutes | 5-10 | Repeat the same pattern for the next weakest command folder. | [ ] |
| 5 | third weakest command | 1-2 minutes | 5-10 | Repeat again until the weakest command folders are no longer badly imbalanced. | [ ] |

Use these recording rules during the pass:

- one utterance per clip
- keep clips near one second
- do not put real command words into `_unknown_`
- keep all speech out of `_background_noise_`
- if multiple speakers are available, split the `_unknown_` and weak-command clips across them

### Optional: Optimize Clips Before Upload

If a capture has too much leading or trailing silence, you can batch-trim the dataset before upload and retraining.

Use [`../scripts/optimize_dataset_clips.py`](../scripts/optimize_dataset_clips.py).

What it does:

- scans the dataset for speech clips
- detects the active speech region by short-frame RMS
- trims leading and trailing silence
- keeps a small pre-roll and post-roll margin
- re-pads the clip back to the fixed one-second training length
- skips `_background_noise_` by default
- backs up the original WAV files before overwriting them
- flags clips where the spoken content itself is longer than the fixed training window

Recommended workflow:

1. stop any active recording
2. run a dry-run first
3. inspect the generated report
4. run the in-place optimization pass
5. retrain from the optimized dataset

Board dry-run:

```bash
python3 /root/kws-training/scripts/optimize_dataset_clips.py \
  --dataset-root /root/kws-training/src/datasets \
  --dry-run
```

Board in-place optimization:

```bash
python3 /root/kws-training/scripts/optimize_dataset_clips.py \
  --dataset-root /root/kws-training/src/datasets
```

Windows host dry-run:

```powershell
py -3 ".\scripts\optimize_dataset_clips.py" `
  --dataset-root ".\src\datasets" `
  --dry-run
```

Windows host in-place optimization:

```powershell
py -3 ".\scripts\optimize_dataset_clips.py" `
  --dataset-root ".\src\datasets"
```

Outputs:

- backups are written under `optimized-backups/<timestamp>/`
- the full JSON report is written to `optimized-backups/<timestamp>/optimize-report.json`

Important limits:

- `_background_noise_` is excluded unless you explicitly pass `--include-background-noise`
- clips whose active speech still exceeds one second are not cropped aggressively; they are reported as skipped so you can re-record them cleanly
- this script does not resample or change the WAV format; it expects the board-standard `16 kHz`, mono, 16-bit PCM clips

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

Default behavior:

- if you do not pass explicit labels, the app trains `deal`, `double`, `hit`, `reset`, and `stand`
- `_unknown_` and `_background_noise_` are still included automatically when present
- the SageMaker trainer first tries to pretrain the DS-CNN backbone on Speech Commands, then fine-tunes on the board dataset
- the board start script now also enables MUSAN from `https://www.openslr.org/resources/17/musan.tar.gz`
- MUSAN clips are mixed into the effective noise pool before fine-tuning

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

### Recommended Board-Driven Request

Use this when you want the default five-command flow explicitly, even if extra historical labels still exist on disk:

```bash
curl -X POST http://<board-ip>:<port>/api/aws/train \
  -H 'Content-Type: application/json' \
  -d '{"labels":["deal","double","hit","reset","stand","_unknown_","_background_noise_"]}'
```

## 4. Manual Workstation-Driven Training

This path is useful when:

- you do not want AWS credentials on the board
- you want to rerun training with different hyperparameters
- you want tighter operator control over job submission

### Build The Trainer Image

```powershell
cd "<repo-root>\\microchip-sama7d65-curiosity\\demos\\key-word-spotter\\kws training\\sagemaker-train"
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
  -WantedWords "deal,double,hit,reset,stand"
```

The returned training output gives you the `model-state.pt` location needed for conversion.

Recommended workstation-driven tuning:

- keep `deal,double,hit,reset,stand` as the initial target set
- leave Speech Commands pretraining enabled unless you are debugging the fine-tune path itself
- keep MUSAN enabled for board-driven retrains unless the external download becomes a problem

## 5. Manual Workstation-Driven Conversion

### Build The Converter Image

```powershell
cd "<repo-root>\\microchip-sama7d65-curiosity\\demos\\key-word-spotter\\kws training\\sagemaker-convert"
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

## 8. Install A Converted Model From The Flask UI

If the board has credentials that can read the models bucket, the Flask UI can browse converted model packages directly from S3.

UI flow:

1. open the `Install Converted Model` panel
2. press `Refresh Model List`
3. review the available converted packages
4. press `Install` for a specific package or `Install Latest Model`

The board will:

1. download the selected archive from the models bucket
2. extract it in a temporary directory
3. run the package `install.sh`
4. copy the model assets into `/opt/demo/models`

After install, restart the runtime app that consumes `/opt/demo/models` if it is already running.

## 9. Deploy The Package To `kws-demo`

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

## 10. Retraining After Adding More Clips

When you add more data:

1. keep the same label names
2. upload or train again from the board
3. compare the new `training-result.json` with previous runs
4. deploy the new package only if the model quality improved

Do not assume a model is good just because the AWS pipeline completed successfully. Review:

- dataset size by label
- validation accuracy
- false positives and missed detections on the board

## 11. Common Failure Modes

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

### Model List Or Install Fails In The Flask UI

Likely causes:

- `KWS_TRAINING_OUTPUT_BUCKET` is missing
- the board can upload datasets through `/IOTCONNECT`, but it does not have credentials that can read the models bucket
- the conversion output prefix does not match `KWS_TRAINING_PIPELINE_OUTPUT_PREFIX`
- the selected archive does not contain `install.sh`

### Training Quality Is Poor

Typical fixes:

- add more clips per label
- add more speaker variation
- remove mislabeled clips
- rebalance labels with very different clip counts
- verify the microphone path and capture quality on the board
