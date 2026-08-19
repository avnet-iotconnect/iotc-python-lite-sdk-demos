# Cloud → edge model push: deploy an LLM to the Ara240 from IOTCONNECT

IOTCONNECT can **store a model in the cloud and push it to a device**, where the demo downloads it, loads it
onto the **Kinara Ara‑2 / NXP Ara240** NPU, and starts serving it — no SSH, no manual file copy. This is
IOTCONNECT's model-management layer on top of the on-device AI: manage models centrally, deploy to one device or
a fleet with a click.

This walkthrough deploys `Qwen2.5-Coder-1.5B` to a FRDM‑IMX95 (`MCLiMX95b`) that **does not have it** — proving
the whole path. Retraining is a separate feature and is intentionally out of scope here.

> Prerequisite: the Ara240 backend is up (runtime + eIQ AAF Connector) — see
> [Enabling the Ara240 backend](../README.md#enabling-the-kinara-ara-2--nxp-ara240-backend). The demo app
> (`app.py`) handles the incoming push automatically; no per-push device action is needed.

---

## 1. Package the model

IOTCONNECT delivers whatever file you upload, so package the **whole Ara240 model directory** (its `model.dvm`
plus `config.json` and the `tokenizer/` folder) into a single `.tar`. From your host, stream it straight off the
board (no board disk used):

```bash
ssh root@<board-ip> "tar -cf - -C /usr/share/llm/Qwen2.5-Coder-1.5B ." > Qwen2.5-Coder-1.5B.tar
```

The tar's top level must contain `model.dvm`, `config.json`, `tokenizer/` (the device extracts it straight into
the model folder). Any Ara240 `model.dvm` bundle works the same way.

## 2. Create the model in IOTCONNECT

**AI Models → My Model → Create Model.**

![Create Model from the My Model list](media/push-model/1-create-model.png)

Fill in the details and choose your `.tar` as the **Model File**:

![Enter model details and select the tar file](media/push-model/2-model-details.png)

| Field | Value | Notes |
|---|---|---|
| **Name** | e.g. `LLM Qwen2.5 1.5B` | Free text |
| **Code** | e.g. `Qwen25C15B` | ⚠️ **3–10 chars, alphanumeric only, must start with a letter** (no `-` or `.`). **The device uses this as the model's name** — it deploys to `/usr/share/llm/<Code>/` and serves it under `<Code>`, so pick something clean and recognizable |
| **Version** | e.g. `1.0.0.0` | |
| **Model Type** | `AI Model` | |
| **Variant** | `NXP` | |
| **Model File** | your `.tar` | The Ara240 model package from step 1 |
| **Convert through sagemaker?** | **unchecked** | Leave off — the `.tar` is already an Ara‑compiled model; conversion would break it |

Save. The model appears in **My Model** with status **Completed**:

![The new model listed under My Model](media/push-model/3-my-model-list.png)

## 3. Push the model to the device

**AI Models → Push Model.** Select the model + version, pick the device template your device is on —
**`genaiflow`** if you imported this repo's template (the screenshots show our booth account's `iMX95genai`) —
choose **Selected devices → `MCLiMX95b`**, and click **Push Model**.

![Push Model to the FRDM device](media/push-model/4-push-model.png)

## 4. Watch it land (the device does the rest)

The demo app receives the push (a `ct:2` module command carrying a presigned S3 URL) and deploys it
automatically. Follow **`model_deploy_status`** on the dashboard:

```
idle → downloading → deploying → loading → ready
```

- **downloading** – pulls the package from S3
- **deploying** – unpacks it into `/usr/share/llm/<Code>/` (handles IOTCONNECT's tar wrapping)
- **loading** – restarts the eIQ AAF Connector so the model loads onto the Ara240
- **ready** – the model is serving; the demo switches `set-backend ara2` / `ara2_model` to it and sends an
  **`OTA_DOWNLOAD_DONE`** ack back to IOTCONNECT

Measured on a FRDM‑IMX95: **~54 s** from *Push* to *ready* (the connector reloads the resident 7B alongside the
new model). Then `ask-llm` answers on the freshly pushed model:

> **ask-llm** *"In one sentence, what is edge AI?"* →
> *"Edge AI is the use of artificial intelligence technology to process and analyze data at the edge of a
> network, enabling real-time decision-making and analysis."* — served by `Qwen25C15B` on the Ara240.

`model_deploy_*` are telemetry attributes; add **`model_deploy_status`**, **`model_deploy_name`**, and
**`model_deploy_detail`** to your device's template (`genaiflow` in this repo) to show the deploy progress on a
dashboard.

---

## How it works (device side)

`app.py` registers a handler for the IOTCONNECT model push and deploys it to the connector:

- **Receiving the push.** IOTCONNECT sends the model as a module command (`ct:2`) with a download URL. The
  `iotconnect-sdk-lite` maps `ct:2` to message type `UNKNOWN` (the `MODULE_COMMAND` id isn't in its type map), so
  the handler is registered under `C2dMessage.UNKNOWN` via `generic_message_callbacks` and filters on `ct == 2`.
- **Deploying.** It downloads the `urls[].Url` file, un-tars it (recursively — IOTCONNECT wraps the upload in its
  own `.tar`) into `/usr/share/llm/<Code>/`, enables `<Code>` in the connector's `server_config.json`, restarts
  the connector, and waits for the model to report `ready` on `/v1/models`.
- **Activating + acking.** It points `ara2_model` at `<Code>` and sets `backend = ara2` (so `ask-llm` serves it),
  publishes `model_deploy_status = ready`, and acks the module command back to IOTCONNECT
  (`OTA_DOWNLOAD_DONE`, or `OTA_DOWNLOAD_FAILED` with the error on failure).

See `on_module_command` / `deploy_model` in [`src/app.py`](../src/app.py).
