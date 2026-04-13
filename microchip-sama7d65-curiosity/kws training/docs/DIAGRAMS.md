# Diagrams

These diagrams describe the full `kws training` system in Mermaid format so they stay editable in the repository.

If your Markdown viewer does not render Mermaid, copy a block into the Mermaid Live Editor or any Markdown tool that supports Mermaid and export it as SVG or PDF.

## 1. System Architecture

```mermaid
flowchart LR
    subgraph Board["Edge Board"]
        UI["Flask UI"]
        Capture["Audio Capture<br/>arecord"]
        Dataset["Dataset Store<br/>datasets/<label>/"]
        App["training_app.py"]
        Bridge["iotconnect_bridge.py"]
    end

    subgraph IoTC["/IOTCONNECT"]
        Device["Device Identity"]
        FileCfg["File Support<br/>bucket + topic"]
        Telemetry["Telemetry + Commands"]
        OTA["OTA / file-download"]
    end

    subgraph AWS["AWS"]
        TBucket["Telemetry Bucket"]
        Trainer["SageMaker Trainer"]
        MBucket["Models Bucket"]
        SFN["Step Functions<br/>conv-*"]
        Converter["SageMaker Converter"]
    end

    subgraph Runtime["Deployed Runtime"]
        Demo["kws-demo"]
        Model["model.tflite + labels.txt"]
    end

    UI --> Capture
    Capture --> Dataset
    Dataset --> App
    App --> Bridge
    Bridge --> Device
    Device --> FileCfg
    Bridge --> Telemetry
    App --> TBucket
    TBucket --> Trainer
    Trainer --> MBucket
    MBucket --> SFN
    SFN --> Converter
    Converter --> MBucket
    OTA --> Demo
    MBucket --> OTA
    Demo --> Model
```

## 2. Initial Provisioning And Setup

```mermaid
flowchart TD
    Start["Start"] --> AWS1["Create or identify S3 buckets"]
    AWS1 --> AWS2["Create SageMaker training role"]
    AWS2 --> AWS3["Provision /IOTCONNECT conversion pipeline"]
    AWS3 --> AWS4["Build and push trainer image"]
    AWS4 --> AWS5["Build and push converter image"]
    AWS5 --> IoTC1["Import kws-training-template.json into /IOTCONNECT"]
    IoTC1 --> IoTC2["Create training device"]
    IoTC2 --> IoTC3["Download device config + cert + key"]
    IoTC3 --> Board1["Copy kws training folder to board"]
    Board1 --> Board2["Place device files on board"]
    Board2 --> Board3["Run src/install.sh"]
    Board3 --> Board4["Set runtime environment variables"]
    Board4 --> Decision{"Board submits<br/>training jobs?"}
    Decision -- Yes --> BoardCreds["Add IAM credentials to board"]
    Decision -- No --> HostOnly["Host launches training manually"]
    BoardCreds --> Run["Start training_app.py"]
    HostOnly --> Run
    Run --> Ready["Open Flask UI and verify /api/state"]
```

## 3. Board-Driven Retraining With Auto-Conversion

```mermaid
sequenceDiagram
    participant User
    participant UI as Flask UI
    participant App as training_app.py
    participant IoTC as /IOTCONNECT
    participant S3T as Telemetry Bucket
    participant Train as SageMaker Trainer
    participant S3M as Models Bucket
    participant SFN as Step Functions conv-*
    participant Conv as SageMaker Converter
    participant Demo as kws-demo

    User->>UI: Select labels and press Start Training
    UI->>App: POST /api/aws/train
    App->>App: Build dataset archive + manifest
    App->>IoTC: Resolve file support + MQTT topic
    App->>S3T: Upload archive and manifest
    App->>IoTC: Publish FILE event
    App->>Train: Create SageMaker training job
    Train->>S3M: Write model-state.pt, model.pt, labels.txt, training-result.json
    App->>Train: Poll training status
    App->>SFN: Start conversion execution
    SFN->>Conv: Launch processing job
    Conv->>S3M: Write model.tflite, package-info.json, zip
    App->>SFN: Poll execution status
    User->>UI: View final package location
    S3M->>Demo: Deploy zip through OTA or file-download
```

## 4. Artifact Lifecycle

```mermaid
flowchart LR
    A["WAV clips<br/>datasets/<label>/"] --> B["Dataset archive<br/>kws-dataset-*.tar.gz"]
    B --> C["Manifest<br/>kws-dataset-*.manifest.json"]
    B --> D["S3 telemetry upload"]
    C --> D
    D --> E["Training job"]
    E --> F["model-state.pt"]
    E --> G["model.pt"]
    E --> H["labels.txt"]
    E --> I["training-result.json"]
    F --> J["Conversion pipeline"]
    H --> J
    I --> J
    J --> K["model.tflite"]
    J --> L["package-info.json"]
    J --> M["conversion-result.json"]
    K --> N["model-only zip"]
    H --> N
    L --> N
    N --> O["OTA / file-download / manual install"]
```

## 5. Upload And Training Mode Selection

```mermaid
flowchart TD
    Start["User triggers upload or training"] --> UploadMode{"Upload mode"}

    UploadMode -- auto --> UploadAuto{"Does device identity expose file support?"}
    UploadMode -- iotconnect --> Native["Use /IOTCONNECT native upload"]
    UploadMode -- direct --> Direct["Use direct boto3 S3 upload"]

    UploadAuto -- Yes --> Native
    UploadAuto -- No --> DirectReady{"Is direct S3 configured?"}
    DirectReady -- Yes --> Direct
    DirectReady -- No --> UploadError["Upload not ready"]

    Native --> TrainingMode{"Training mode"}
    Direct --> TrainingMode

    TrainingMode -- auto --> TrainAuto{"Are direct SageMaker settings ready?"}
    TrainingMode -- direct-sagemaker --> DirectTrain["Launch trainer image"]
    TrainingMode -- iotconnect-conversion --> ConvertOnly["Launch conversion only"]

    TrainAuto -- Yes --> DirectTrain
    TrainAuto -- No --> ConvertReady{"Are conversion-only settings ready?"}
    ConvertReady -- Yes --> ConvertOnly
    ConvertReady -- No --> TrainError["Training workflow not ready"]

    DirectTrain --> AutoConvert{"Auto-convert enabled and converter ready?"}
    AutoConvert -- Yes --> ConvertOnly
    AutoConvert -- No --> Done["Stop after training output"]
    ConvertOnly --> Final["Final zip produced"]
```

## 6. Deployment Back To `kws-demo`

```mermaid
flowchart TD
    Package["Converted model zip"] --> DeployChoice{"Deployment path"}
    DeployChoice -- OTA --> OTA["Publish package in /IOTCONNECT"]
    DeployChoice -- Command --> FileCmd["Send file-download command"]
    DeployChoice -- Manual --> SCP["Copy zip to board"]

    OTA --> Install["Extract zip and run install.sh"]
    FileCmd --> Install
    SCP --> Install

    Install --> Assets["models/model.tflite<br/>models/labels.txt<br/>models/package-info.json"]
    Assets --> Runtime["kws-demo loads new model"]
    Runtime --> Verify["Verify telemetry, label behavior, and package metadata"]
```

## 7. Credential Boundaries

```mermaid
flowchart LR
    subgraph Board["Board Secrets"]
        Cert["/IOTCONNECT device cert"]
        Key["/IOTCONNECT device key"]
        AwsCreds["Optional board AWS creds"]
    end

    subgraph Workstation["Operator Workstation"]
        Cli["AWS CLI profile"]
        Docker["Docker Desktop"]
    end

    subgraph Cloud["Cloud Identities"]
        IamUser["Operator IAM user or SSO role"]
        SmRole["SageMaker execution role"]
        IoTCRole["/IOTCONNECT provisioned roles"]
        IoTCAuth["/IOTCONNECT identity + file auth"]
    end

    Cli --> IamUser
    Docker --> IamUser
    AwsCreds --> IamUser
    Cert --> IoTCAuth
    Key --> IoTCAuth
    IoTCAuth --> IoTCRole
    IamUser --> SmRole
```

## Suggested Uses

- use diagram 1 in the top-level project overview
- use diagram 2 when onboarding someone to the setup sequence
- use diagram 3 in demos and design reviews
- use diagram 4 when discussing artifact contracts between stages
- use diagram 5 when debugging why a workflow did or did not start
- use diagram 6 when handing off model deployment to the team running `kws-demo`
- use diagram 7 when discussing security and credential placement
