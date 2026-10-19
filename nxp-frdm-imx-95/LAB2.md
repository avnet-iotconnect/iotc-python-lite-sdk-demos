# Lab 2: Enable the NPU and Explore other NXP eIQ GenAI Flow Models

This lab continues the [`GETTING_STARTED.md`](./GETTING_STARTED.md) guide

## Table of Contents

- [Lab 2: Enable the NPU and Explore other NXP eIQ GenAI Flow Models](#lab-2-enable-the-npu-and-explore-other-nxp-eiq-genai-flow-models)
  - [Table of Contents](#table-of-contents)
  - [1. Introduction / Overview](#1-introduction--overview)
  - [2. Prerequisites](#2-prerequisites)
    - [Hardware](#hardware)
  - [3. Leveraging the Neutron NPU](#3-leveraging-the-neutron-npu)
    - [3.1. Install and enable the Neutron NPU](#31-install-and-enable-the-neutron-npu)
    - [3.2. Comparing CPU vs. NPU performance](#32-comparing-cpu-vs-npu-performance)
  - [4. Vision Language Model (ask-vlm)](#4-vision-language-model-ask-vlm)
    - [4.1. Install](#41-install)
    - [4.2. Use the Model](#42-use-the-model)
  - [5. Voice Assistant (voice-start)](#5-voice-assistant-voice-start)
    - [5.1. Audio hardware setup](#51-audio-hardware-setup)
    - [5.2. Using the voice assistant](#52-using-the-voice-assistant)
    - [5.3. (Optional) Tuning](#53-optional-tuning)
  - [6. RAG: Ground Answers in Your Own Documentation (set-rag)](#6-rag-ground-answers-in-your-own-documentation-set-rag)
    - [6.1. Build the database](#61-build-the-database)
    - [6.2. Calibrate the ambiguity threshold](#62-calibrate-the-ambiguity-threshold)
    - [6.3. Use it](#63-use-it)

## 1. Introduction / Overview

The NXP i.MX 95 includes an integrated Neural Processing Unit (NPU) designed to accelerate supported machine-learning operations.

Compared with CPU execution, the NPU can:

- Improve inference latency.
- Reduce CPU utilization.
- Reduce power consumption.
- Support continuous AI workloads.
- Allow the CPU to handle application logic, networking, sensors, and /IOTCONNECT communication.

The NPU is used only when the model, runtime, data types, and operators are supported. Unsupported operations may fall back to CPU execution.

## 2. Prerequisites

- Complete the [`GETTING_STARTED.md`](./GETTING_STARTED.md) guide

### Hardware

- USB Camera: Vision model testing
- Microphone: Voice model testing (If your USB camera has a built-in microphone, it can be used for this purpose)

## 3. Leveraging the Neutron NPU

The Neutron NPU needs a large reserved DMA/CMA memory pool for LLM inference (the default `CmaTotal` is only
~960 MB; NXP requires >3 GB). The whinlatter FRDM image ships **no** FRDM Neutron device tree — the boot
partition holds only the default `imx95-15x15-frdm.dtb` and peripheral variants — so this repo provides the
missing one: **[`imx95-15x15-frdm-neutron.dtb`](imx95-15x15-frdm-neutron.dtb)**
(sha256 `5a7a0bf478f1395f374d9b207aeb7a1cc277f0e9a5482afa1e0d5f2c4240b09e`).

It is the stock whinlatter `imx95-15x15-frdm.dtb` with NXP's EVK Neutron overlay merged in — the delta is a
4 GB `shared-dma-pool` reserved at `0x1_0000_0000` (the upper half of an 8 GB board's DDR) plus a
`memory-region` reference on the `imx95-neutron@4ab00004` node.

### 3.1. Install and enable the Neutron NPU

1. Download the **[`imx95-15x15-frdm-neutron.dtb`](imx95-15x15-frdm-neutron.dtb)**
2. Naviagte to the download location and right-click anywhere in the windows folder and select **Open in Terminal**
3. Use `scp` to copy the DTB to the board's boot partition (replace `<board-ip>` with the actual IP address of your board):
    ```bash
    scp imx95-15x15-frdm-neutron.dtb root@<board-ip>:/run/media/boot-mmcblk0p1/
    ```
4. Reboot the board and, using the serial console, interrupt the boot process to access the U-Boot prompt by pressing any key when prompted. The board will boot into U-Boot and display the prompt `u-boot=>`.
5. Select it from the **U-Boot** prompt:

    ```text
    u-boot=> setenv fdtfile imx95-15x15-frdm-neutron.dtb
    u-boot=> saveenv    # (optional) persist the choice across reboots
    u-boot=> boot
    ```

6. After Linux comes up, verify:

    ```bash
    grep -i cma /proc/meminfo   # CmaTotal now shows the enlarged Neutron pool (>3 GB)
    ls /dev/neutron0            # NPU device present
    ```

> [!NOTE]
> To revert, set `fdtfile` back to the default `imx95-15x15-frdm.dtb` (`setenv fdtfile imx95-15x15-frdm.dtb; saveenv; boot`). The original DTB is never touched.

> [!TIP]
> No serial console? The U-Boot environment can also be edited from Linux userspace with NXP's `fw_setenv` /
> `fw_printenv` (`fw_env`) tools — `fw_setenv fdtfile imx95-15x15-frdm-neutron.dtb` — which lets you switch the DTB
> without a console. It needs a matching `/etc/fw_env.config` for this board's eMMC environment; treat it as
> experimental until confirmed on your image.

### 3.2. Comparing CPU vs. NPU performance

A typical performance experiment from the /IOTCONNECT command panel:

1. `set-backend cpu` → `ask-llm Tell me about the i.MX 95 processor.` → note `llm_tps`
2. `set-backend neutron` → repeat the same prompt → compare `llm_tps` and `llm_ttft`

> [!NOTE]
> The first response with the NPU takes ~2 minutes while the model is compiled for the NPU (watch `llm_load_time`).

## 4. Vision Language Model (ask-vlm)

The GenAI Flow repository also ships a **VLM submodule** (SmolVLM2-256M/500M) that answers natural-language questions
about images — this demo wires it to a USB camera so you can ask about the live scene from /IOTCONNECT.

### 4.1. Install

The VLM submodule was fetched and installed in the [GETTING_STARTED](GETTING_STARTED.md). If you missed that step, run it now with the following command to install the VLM submodule:

```bash
cd /root/vlm && ./install.sh
```

1. Connect a UVC USB webcam to the board's **USB A** port and find its device node with the following command:

```bash
v4l2-ctl --list-devices
```

You should see your device appearing as `/dev/video##` (e.g. `/dev/video52`).

2. Set `camera_device` in `/opt/demo/genai-config.json` if yours differs, along with `vlm_model` (`smolvlm-256M` default, or `smolvlm-500M`)
and `vlm_precision` (`q8` default, or `fp32`) — or switch the vision model from the cloud at any time with the
`set-vlm` command (e.g. `set-vlm smolvlm-500M`), no SSH needed.

### 4.2. Use the Model

- Send the `ask-vlm` command from /IOTCONNECT — with no argument it describes the scene
- Or ask something specific like `Is there a person in the room?`. The app captures a fresh frame via GStreamer, runs the VLM (models download on first use), and publishes `vlm_response` plus performance telemetry.

## 5. Voice Assistant (voice-start)

The `voice-start` command turns the board into a fully offline voice assistant using GenAI Flow's complete pipeline:

**"Hey NXP"** wake-word detection (VIT) → speech-to-text (Moonshine) → LLM (Danube, CPU or Neutron NPU per `set-backend`) → streaming text-to-speech (VITS), with every exchange published to /IOTCONNECT.

### 5.1. Audio hardware setup

The GenAI Flow auto-detects audio devices. On a FRDM-IMX95 with a USB webcam this means the webcam's microphone (if equipped) for
capture and the **MQS 3.5 mm jack** for TTS playback. Plug in headphones or a powered speaker to hear the replies
(or start with `voice-start text` for text responses).

>[!TIP]
> A USB headset with echo/noise cancellation improves wake-word and transcription accuracy.

> [!TIP]
> Override `capture_device` / `playback_device` in `/opt/demo/genai-config.json` to select it (ALSA names from `arecord -l` / `aplay -l`, e.g. `sysdefault:CARD=H570e`).

### 5.2. Using the voice assistant

1. Send the command `voice-start` and wait for `voice_status` to reach `listening` (~1–3 minutes while models load; longer on the
   Neutron backend due to the NPU compile).
2. Say **"Hey NXP"**, pause until `voice_status` shows `capturing` (or you hear the tone), then ask your question.
3. The answer streams out loud and lands in `voice_question` / `voice_response` / `voice_exchanges` telemetry.
4. The session re-arms for the next wake word; send `voice-stop` to end it.

> [!TIP]
> Speak the wake word, pause, *then* speak your command/question. Running them together can put "Hey NXP" into the transcription itself.

### 5.3. (Optional) Tuning

- **Set the capture gain first (STT accuracy depends on it).** The microphone capture level is very low by default
  on this image — low enough that speech-to-text still *works*, but transcription accuracy jumps dramatically once
  the gain is raised (true for both the webcam mic and USB microphones). Turn it up with `alsamixer`:
  
  ```bash
  alsamixer                 # press F6, pick the capture card (your mic); F4 for Capture view;
                            # raise the Capture/Mic level with the Up arrow (aim high, ~80–100%)
  alsactl store            # persist the levels across reboots
  ```
  
  Or set it non-interactively, e.g. `amixer -c <card> sset 'Mic' 100%` (use `arecord -l` to find the card and
  `amixer -c <card> scontrols` for the exact control name). Re-run the [venue mic check](demo-flow.md#venue-mic-check-run-after-any-board-move-before-doors-open) — you want speech seconds at **2000+ RMS**.
- **Getting cut off mid-question?** GenAI Flow ends speech capture after only 200 ms of silence by default, which
  truncates questions to their first word or two. Raise it (800 ms works well) in
  `/root/eiq_genai_flow/adapters/stt/stt_adapter.py`:

  ```python
  vad_min_silence_duration_ms: int = 800
  ```

  Restart the voice session (`voice-stop` / `voice-start`) to apply.
- **Latency vs. accuracy**: `stt_model` in `/opt/demo/genai-config.json` selects the transcriber —
  `moonshine-tiny` (fastest, default), `moonshine-base`, or `whisper-small.en` (most accurate).

## 6. RAG: Ground Answers in Your Own Documentation (set-rag)

Small language models hallucinate facts. RAG (Retrieval-Augmented Generation) fixes that by retrieving relevant
passages from an on-device vector database and injecting them into the prompt — turning the board into an offline
**"ask the manual"** assistant. This demo ships a knowledge base about the FRDM-IMX95 itself
([rag-db/FRDM95_hand_made_chunks.json](rag-db/FRDM95_hand_made_chunks.json)), so the board can answer questions about
its own setup, commands, and measured performance with real numbers instead of inventions.

### 6.1. Build the database

- Connect to board vis serial console and enter the following commands to build the RAG database:

```bash
cd /root/eiq_genai_flow/rag/src/data
mkdir -p medical-backup
mv chunked_files/Medical_*.json medical-backup/           # remove the sample medical content
cp rag_database.pkl medical-backup/                       # keep a backup
# copy FRDM95_hand_made_chunks.json (from this repo's rag-db/) into chunked_files/, then:
cd /root/eiq_genai_flow/rag/src
echo "User guide for the NXP FRDM i.MX 95 development board." | \
  python3 -m rag.preprocessing.generate_embeddings -f all
```

> [!TIP]
> To use your own content, write a chunk file in the same JSON format — **one single-chunk group per passage**, as
> in the shipped file — and rebuild; any product manual, datasheet, or procedure text works.

You can also manage the database **from the cloud**, no SSH needed: `rag-add <document URL> [name]` downloads a
document (upload it via IOTCONNECT to get a URL), chunks and embeds it on the board (progress in `rag_status` /
`rag_detail`); `rag-show <name>` publishes a preview of a document's chunks; `rag-remove <name>` deletes it.

### 6.2. Calibrate the ambiguity threshold

GenAI Flow's query classifier rejects questions as "ambiguous" when retrieval similarity is below
`similarity_threshold` (default 0.65) in `/root/eiq_genai_flow/config.py`. With MiniLM embeddings and hand-made
chunks, correct matches typically score 0.31–0.45 (e.g. *"How do I expand the root filesystem?"* scores 0.31
against its own chunk), so lower it:

```python
similarity_threshold: float = 0.30
```

### 6.3. Use it

Toggle grounding from /IOTCONNECT with `set-rag on` / `set-rag off` (reflected in the `llm_rag` telemetry
attribute). It applies to `ask-llm`, the voice assistant, and `run-benchmark`. Example, with RAG on:

> **ask-llm** `How do I expand the root filesystem?` →
> *"The stock FRDM i.MX 95 demo image only allocates about 11 GB of the 32 GB eMMC to the root filesystem. Expand it
> with: parted -s /dev/mmcblk0 resizepart 2 100% followed by resize2fs /dev/mmcblk0p2"* — verbatim from the docs.