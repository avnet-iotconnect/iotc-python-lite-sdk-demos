# eIQ GenAI Flow Edge LLM Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the NXP FRDM i.MX 95 to an **on-device Generative AI** demo built around
NXP's [eIQ GenAI Flow](https://www.nxp.com/design/design-center/software/embedded-software/eiq-genai-flow-conversational-ai-software-pipeline-on-edge-devices:GEN-AI-FLOW)
conversational AI pipeline, with live **LLM performance telemetry** (tokens/sec, time-to-first-token, CPU, memory,
temperature) streamed to /IOTCONNECT.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for this board](../README.md) before proceeding.

> [!TIP]
> Demoing this at a booth or customer meeting? Follow the step-by-step [demo flow guide](demo-flow.md) —
> every feature with expected results, time-to-result, the telemetry to point at, and a failure playbook.
> A complete inventory of every AI model in the demo — function, footprint, measured performance — is in
> [MODELS.md](MODELS.md).

## 1. Introduction

[eIQ GenAI Flow](https://github.com/nxp-appcodehub/dm-eiq-genai-flow-demonstrator) is NXP's modular, end-to-end
software pipeline for running Generative AI at the edge. It combines wake-word detection (VIT), speech-to-text
(Whisper / Moonshine), Retrieval-Augmented Generation (RAG), a small language model (Danube-500M, derived from the
Llama family), and text-to-speech (VITS) — all running locally on the i.MX 95.

This expansion demo connects that pipeline to /IOTCONNECT so you can:

* **Prompt the on-device LLM from the cloud** with the `ask-llm` command and see the response and measured performance
  come back as telemetry.
* **Ask a Vision Language Model about the camera view** with the `ask-vlm` command — a USB webcam frame is captured
  and answered about by SmolVLM2 running on the board (see [Vision Language Model](#vision-language-model-ask-vlm)).
* **Run the official GenAI Flow benchmark** (`run-benchmark`) and publish its metrics (TTFT, tokens/sec, CPU/memory
  averages) to your dashboard.
* **Switch models and backends** (`set-model`, `set-backend`) to compare CPU vs. eIQ Neutron NPU performance.
* **Monitor the board** continuously (CPU %, memory, SoC temperature) while models are running.

### Execution backends

| Backend | Status | Notes |
|---|---|---|
| Cortex-A55 CPU (6 cores) | ✅ Supported | Default. Runs Danube-500M q8/q4 |
| eIQ Neutron NPU | ✅ Confirmed on whinlatter FRDM | `set-backend neutron`; requires i.MX 95 **B0** silicon (SoC revision 2.0), an **8 GB** board, and booting a Neutron device tree that reserves the enlarged CMA pool — see [Enabling the Neutron NPU](#enabling-the-neutron-npu). The benchmark table's NPU numbers were measured this way on a whinlatter (LF6.18.2-1.0.0) FRDM. |
| Kinara Ara-2 / NXP Ara240 discrete NPU module | ✅ Supported (setup required) | `set-backend ara2` runs `ask-llm` on the Ara240 M.2 module via NXP's eIQ AAF Connector — enables much larger LLMs (Qwen2.5-7B) at interactive speed. Requires the NXP Ara240 runtime + connector (account-gated download) — see [Enabling the Ara240 backend](#enabling-the-kinara-ara-2--nxp-ara240-backend) |

### Measured performance

Measured on a FRDM-IMX95 (BSP LF6.18.2, `danube-500M-q8`, identical prompt; load time excluded from
performance — see [MODELS.md](MODELS.md) for the full matrix: six LLM configurations plus the VLM and STT tables):

| Metric | CPU (6× Cortex-A55) | eIQ Neutron NPU |
|---|---|---|
| Tokens/sec | 10.1 | **13.7** (+35%) |
| Time to first token | 0.74 s | 0.48 s |
| Model load (separate) | ~44 s | ~129 s (includes NPU model compile) |

## 2. Requirements

* Completed [FRDM i.MX 95 quickstart](../README.md) (starter demo onboarded and working in `/opt/demo`)
* NXP Linux BSP **LF6.18.2-1.0.0** ("whinlatter", kernel `6.18.2`) — the release this flow runs on. Check
  yours with `uname -r`, and see the [flashing guide](../FLASHING.md) / [BSP-UPGRADE.md](docs/BSP-UPGRADE.md)
  to install it.
  > [!WARNING]
  > **Do not use the newer LF6.18.20_2.0.0 ("wrynose").** It ships **Python 3.14 only**, and eIQ GenAI Flow's
  > core is distributed as **`cpython-313` compiled binaries** that Python 3.14 cannot load — the stack does
  > not run there (verified on hardware). Revisit only when NXP publishes `cpython-314` GenAI Flow builds.
* At least **16 GB free storage** on the board for GenAI Flow and its models
* Internet access on the board (GenAI Flow is fetched from GitHub, ~1.5 GB; the vision model downloads on first use)

> [!IMPORTANT]
> The stock NXP demo image only allocates ~11 GB of the 32 GB eMMC to the root filesystem, leaving too little free
> space for GenAI Flow. Expand the root partition to use the full eMMC first (safe to do online):
>
> ```bash
> parted -s /dev/mmcblk0 resizepart 2 100%
> resize2fs /dev/mmcblk0p2
> df -h /   # should now show ~28 GB total
> ```
* (Optional) USB headset or USB speaker + microphone if you want the full voice pipeline (`-i vasr -o tts`)

## 3. Install NXP eIQ GenAI Flow

NXP delivers the eIQ GenAI Flow demonstrator as a separate GitHub repository whose compiled modules and models are
Git LFS objects (~1.5 GB). Everything below runs **on the board** — nothing needs to be installed on your PC.

1. Fetch the demonstrator (this stages both the `eiq_genai_flow` pipeline and its `vlm` vision submodule):

   ```bash
   curl -sL https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-95/genai-flow-demo/src/get-genai-flow.sh | bash
   ```

   It prints one `OK … MB … filename` line per file — 70 lines, about 1.5 GB (the 495 MB Danube LLM is the
   largest) — and ends with *"all LFS files resolved"*. If it ends with `!!` instead, the board's internet
   connection dropped: simply run the same line again.

2. Install both packages:

   ```bash
   cd /root/eiq_genai_flow && ./install.sh
   cd /root/vlm && ./install.sh
   ```

   > [!NOTE]
   > The whinlatter image ships **Python 3.13**, which is what eIQ GenAI Flow's compiled modules
   > (`cpython-313`) require — so `install.sh` and `eiq_genai_flow.py` run under the stock `python3` with no
   > extra steps. (This is why the demo stays on whinlatter; see the BSP warning under Requirements.)

3. Sanity-check it standalone before wiring up /IOTCONNECT — keyboard in, text out:

   ```bash
   cd /root/eiq_genai_flow && python3 eiq_genai_flow.py -i keyb -o text -m danube-500M-q8
   ```

   Type a question at the prompt; an answer means the install is complete. (The first `ask-vlm` later will
   download the SmolVLM2 vision model, ~1–2 minutes, one time only.)

> [!NOTE]
> If you install GenAI Flow somewhere other than `/root/eiq_genai_flow`, edit the `genai_dir` field in
> `/opt/demo/genai-config.json` after step 5 below.

> [!WARNING]
> Prefer to get the repository onto a PC yourself? Then you **must** clone it with Git LFS installed
> (`git lfs install` before `git clone --single-branch -b release/v3.0 https://github.com/nxp-appcodehub/dm-eiq-genai-flow-demonstrator`),
> and on Windows clone with `--config core.autocrlf=false` or the Linux scripts arrive with CRLF line endings.
> GitHub's **"Download ZIP"** does *not* work — it delivers 130-byte LFS placeholder files instead of the binaries,
> and `install.sh` / `eiq_genai_flow.py` then fail with errors such as `No module named 'shared_utils'`. The
> board-side one-liner above sidesteps all of this. (The `dm-eiq-genai-flow-lib-v1.0.0.tgz` file on our download
> server is **not** a copy of the demonstrator either — it is a pruned library subset for a different demo.)

## 4. Change Device Template

Before installing, change your device's template to `genaiflow` in the /IOTCONNECT online platform:

1. Open [console.iotconnect.io](https://console.iotconnect.io) and navigate to your device's page.
2. Locate the **Template** field (mid-left on the page) and click the edit icon.
3. Select the `genaiflow` template from the drop-down and save.

> [!TIP]
> If the `genaiflow` template is not yet present in your /IOTCONNECT instance, import it from
> [genai-flow-template.json](genai-flow-template.json) via **Templates → Create Template → Import**.

## 5. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget -O package.tar.gz https://downloads.iotconnect.io/partners/nxp/packages/frdm-imx95-genai-flow-demo-v1.0.2.tgz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

> [!NOTE]
> The demo package is hosted on /IOTCONNECT's download server, not in Git. To build it yourself from the `src/`
> files in this repository (e.g. after local edits), see [Customize and Rebuild](#14-customize-and-rebuild-optional).

### Run

```bash
python3 app.py
```

> [!TIP]
> For hands-off operation (booth staff, colleagues), copy [board-readme.txt](board-readme.txt) to the board as
> `/root/readme.txt` — anyone can then `cat readme.txt` and paste its health-check block to verify the demo
> services (app, camera server, MCP server) and get the board's IP. Note it assumes a board prepared with
> [workshop-install.sh](src/workshop-install.sh), which installs the `genai-app`/`genai-camera` systemd services
> (the `genai-mcp` service additionally needs the [MCP server](#10-agent-llm-with-real-board-tools-ask-agent)
> installed and a matching unit created). On a plain install, start the app with `python3 app.py` instead.


## 6. Using the Demo

Once running, system telemetry streams to /IOTCONNECT every 10 seconds. Use the **Command** panel on your device page
to interact with the LLM:

| Command | Argument | What it does |
|---|---|---|
| `ask-llm` | prompt text, e.g. `What is the capital of France?` | Runs the prompt through the on-device LLM. The command is acknowledged immediately; the response arrives as `llm_response` telemetry along with `llm_ttft`, `llm_gen_time`, `llm_tps`, and `llm_token_count` |
| `ask-vlm` | *(optional)* question, e.g. `Is there a person in the room?` | Captures a frame from the USB camera and answers the question about it with SmolVLM2. Response arrives as `vlm_response` telemetry with `vlm_vision_time`, `vlm_ttft`, and `vlm_tps`. Defaults to "Describe what you see in this image." |
| `ask-agent` | request needing live data, e.g. `what time is it` | Function calling: the LLM picks a real board tool (time, temperature, memory, uptime, IP), the board executes it, and the grounded answer plus the full reasoning chain arrive as `agent_*` telemetry. See [Agent](#10-agent-llm-with-real-board-tools-ask-agent) |
| `agent-start` | — | Pre-warms the agent session (~1 min) so the first question answers in seconds — send at booth open |
| `agent-stop` | — | Stops the agent’s persistent LLM session (it also auto-stops after 60 idle minutes — `agent_idle_timeout_s`) |
| `voice-start` | *(optional)* `tts` (default) or `text` | Starts the wake-word voice assistant ("Hey NXP" → speech-to-text → LLM → text-to-speech). Each exchange publishes `voice_question`, `voice_response`, and `voice_exchanges`; session state is in `voice_status` |
| `voice-stop` | — | Stops the voice assistant session |
| `set-stt` | `moonshine-tiny`, `moonshine-base`, or `whisper-small.en` | Selects the voice transcriber (speed vs. accuracy). Applies on the next `voice-start` |
| `set-vlm` | `smolvlm-256M` or `smolvlm-500M`, optional precision `q8` (default) or `fp32` | Selects the vision model for `ask-vlm` — the 500M gives richer, more grounded descriptions at roughly half the decode speed. Applies on the next `ask-vlm`, which reloads the model (a first-ever load also downloads it) |
| `run-benchmark` | *(optional)* extra CLI args, e.g. `-i vasr -o tts` | Runs GenAI Flow's official benchmark mode (`-r -b`) and publishes `bench_*` metrics. Defaults to keyboard/text mode so no audio hardware is needed |
| `set-model` | `danube-500M-q8`, `danube-500M-q4`, any GGUF model name from `/opt/llama/models` (e.g. `qwen2.5-1.5b-instruct-q4_k_m`), or an Ara240 model served by the AAF connector | Selects the LLM used for subsequent commands. GGUF models run via llama.cpp on the CPU; picking an Ara240 model switches the backend to `ara2` automatically. An invalid name returns the list of available models |
| `set-backend` | `cpu`, `neutron`, or `ara2` | Selects where `ask-llm` runs: CPU, eIQ Neutron NPU, or the Kinara Ara-2 / Ara240 module (see the backend sections above/below) |
| `set-rag` | `on` or `off` | Toggles RAG grounding for `ask-llm`, the voice assistant, and `run-benchmark` (see [RAG](#9-rag-ground-answers-in-your-own-documentation-set-rag)) |
| `rag-add` | document URL, optional name | Downloads a document (IOTCONNECT's file upload provides a URL), chunks and embeds it into the on-device RAG database — watch `rag_status` |
| `rag-show` | document name | Publishes a preview of a document's chunks (`rag_preview` telemetry) |
| `rag-remove` | document name | Removes a document from the RAG database |
| `get-ip` | — | Returns the board's local IP address |
| `file-download` | package URL | Self-update with a new demo package |

> [!NOTE]
> The **first** `ask-llm` after boot takes noticeably longer while the model is loaded (and downloaded on first ever
> use) — watch `llm_load_time`. Subsequent prompts are faster. While a prompt or benchmark is running, `genai_status`
> reports `generating` / `benchmarking`.

<a name="enabling-the-neutron-npu"></a>
### Enabling the Neutron NPU

The Neutron NPU needs a large reserved DMA/CMA memory pool for LLM inference (the default `CmaTotal` is only
~960 MB; NXP requires >3 GB). The whinlatter FRDM image ships **no** FRDM Neutron device tree — the boot
partition holds only the default `imx95-15x15-frdm.dtb` and peripheral variants — so this repo provides the
missing one: **[`imx95-15x15-frdm-neutron.dtb`](imx95-15x15-frdm-neutron.dtb)**
(sha256 `5a7a0bf478f1395f374d9b207aeb7a1cc277f0e9a5482afa1e0d5f2c4240b09e`).

It is the stock whinlatter `imx95-15x15-frdm.dtb` with NXP's EVK Neutron overlay merged in — the delta is a
4 GB `shared-dma-pool` reserved at `0x1_0000_0000` (the upper half of an 8 GB board's DDR) plus a
`memory-region` reference on the `imx95-neutron@4ab00004` node. This exact DTB is what produced the NPU
column of the benchmark table above (verified on whinlatter, kernel `6.18.2-1.0.0`: `CmaTotal` ≈ 5.1 GB,
danube-500M-q8 at 13.7 tok/s). To rebuild it yourself instead of trusting the binary, decompile with
`dtc -I dtb -O dts`, add those two nodes, and recompile — or merge NXP's `imx95-19x19-evk-neutron.dtso`
from the linux-imx kernel source with `fdtoverlay`.

Install it alongside the stock DTB (**nothing is overwritten**):

```bash
# From this repo's genai-flow-demo/ directory on your host PC
scp imx95-15x15-frdm-neutron.dtb root@<board-ip>:/run/media/boot-mmcblk0p1/
```

Select it from the **U-Boot** prompt over the serial console (interrupt boot to reach `u-boot=>`):

```text
u-boot=> setenv fdtfile imx95-15x15-frdm-neutron.dtb
u-boot=> saveenv    # persist the choice across reboots (omit for a one-time try)
u-boot=> boot
```

After Linux comes up, verify:

```bash
grep -i cma /proc/meminfo   # CmaTotal now shows the enlarged Neutron pool (>3 GB)
ls /dev/neutron0            # NPU device present
```

To revert, set `fdtfile` back to the default `imx95-15x15-frdm.dtb` (`setenv fdtfile imx95-15x15-frdm.dtb; saveenv;
boot`). The original DTB is never touched.

> [!TIP]
> No serial console? The U-Boot environment can also be edited from Linux userspace with NXP's `fw_setenv` /
> `fw_printenv` (`fw_env`) tools — `fw_setenv fdtfile imx95-15x15-frdm-neutron.dtb` — which lets you switch the DTB
> without a console. It needs a matching `/etc/fw_env.config` for this board's eMMC environment; treat it as
> experimental until confirmed on your image.

> [!NOTE]
> This requires an **8 GB** board — the Neutron pool reserves the upper 4 GB of DDR (`0x1_0000_0000`–`0x2_0000_0000`),
> which a 4 GB board does not have. General-purpose RAM drops to ~4 GB, which is why the demo app keeps only one
> LLM session resident at a time.

### Comparing CPU vs. NPU performance

A typical performance experiment from the /IOTCONNECT command panel:

1. `set-backend cpu` → `ask-llm Tell me about the i.MX 95 processor.` → note `llm_tps`
2. `set-backend neutron` → repeat the same prompt → compare `llm_tps` and `llm_ttft`

The Neutron backend requires booting the Neutron device tree from [Enabling the Neutron NPU](#enabling-the-neutron-npu),
and its first response takes ~2 minutes longer while the model is compiled for the NPU (watch `llm_load_time`).

### Enabling the Kinara Ara-2 / NXP Ara240 backend

`set-backend ara2` runs `ask-llm` on the Kinara Ara-2 (sold by NXP as the **Ara240** M.2 module) instead of the
CPU or Neutron NPU. The demo talks to the module through NXP's **eIQ AAF Connector** — an OpenAI-compatible REST
server (`/v1/chat/completions`) in front of the Ara240 runtime — so `ask-llm` works unchanged, just on the
discrete NPU and with much larger models.

**Where to get the software** — NXP's **Ara Software Development Kit** page (an NXP account is required; these are
account-gated downloads, **not** NDA):

<https://www.nxp.com/design/design-center/software/embedded-software/ara-software-development-kit:ARA-SDK>

From that page's **Downloads** tab, get:

| Component | What it is | Which to pick |
|---|---|---|
| **Ara2 Runtime SDK** | Proxy daemon, `libaraclient`, firmware, Python bindings, `rt-sdk-ara2.service` | **Match your BSP.** The **`2.0.4` `.deb`** for BSP **LF6.18.2‑1.0.0**; the **`2.1.1` `.bin`** for **LF6.18.20_2.0.0**+ (where the `uiodma` PCIe driver ships inside the kernel image). A runtime built for a *newer* BSP will fail to bring up the module — `modprobe uiodma` reports the module is missing. Check your board with `uname -r`. |
| **eIQ Connector** (`eiq-aaf-connector`) | The REST server this demo's `ara2` backend calls | The `.deb` (also open source: `github.com/nxp-imx-support/eiq-aaf-connector`) |
| *(optional)* **LLM Edge Studio** | NXP's standalone GUI launcher — handy for a booth screenshot | The `.deb` |

**Models** are separate and **public** (Apache‑2.0) on Hugging Face — `model.dvm` files already compiled for the
Ara240, so no compiler is needed:
[`nxp/Qwen2.5-7B-Instruct-Ara240`](https://huggingface.co/nxp/Qwen2.5-7B-Instruct-Ara240) and
[`nxp/Qwen2.5-Coder-1.5B-Ara240`](https://huggingface.co/nxp/Qwen2.5-Coder-1.5B-Ara240). Compiling *your own*
models instead needs the full Ara SDK (an x86_64 host + a compile license key) — see
[docs/ARA2-ENABLEMENT-REQUEST.md](docs/ARA2-ENABLEMENT-REQUEST.md).

**Bring-up outline** (on the board): install the BSP-matched Runtime SDK (its `dpkg -i` sets up
`rt-sdk-ara2.service`), start it (`systemctl start rt-sdk-ara2`) and confirm the module is bound (`lspci -d
1e58: -k` shows `Kernel driver in use: uiodma`); fetch a model (`fetch_models --repo-id
nxp/Qwen2.5-7B-Instruct-Ara240`); enable it in the connector's `server_config.json` and run the connector on
**port 8100** (its default is 8000, which this demo's MCP server already uses). Point `ara2_aaf_url` /
`ara2_model` in `/opt/demo/genai-config.json` at your connector URL and model name, then from /IOTCONNECT:
`set-backend ara2` and `ask-llm`.

**Measured on this board** (FRDM-IMX95 + Ara240, `rt-sdk-ara2` 2.0.4, streaming `/v1/chat/completions`):

| Model (Ara240) | TTFT | tok/s | vs. same-size on CPU |
|---|---|---|---|
| Qwen2.5-Coder-1.5B | 0.51 s | **18.7** | 1.5B on A55 CPU: 5.7 tok/s → **~3.3× faster** |
| Qwen2.5-7B-Instruct | 2.06 s | **5.1** | a 7B at CPU-1.5B speed — 7B quality, interactive |

Full methodology and the CPU/Neutron comparison: [MODELS.md](MODELS.md).

**Deploy models from the cloud.** Once the Ara240 backend is running, you can **push a new model to the device
straight from IOTCONNECT** — upload it once, hit *Push Model*, and the board downloads it, loads it onto the
Ara240, and starts serving it (no SSH). Step-by-step with screenshots: [docs/MODEL-PUSH.md](docs/MODEL-PUSH.md).

### Metrics notes

* For `ask-llm`, token counts (and therefore tokens/sec) are **estimated** from response length (~4 chars/token)
  unless GenAI Flow prints exact figures, in which case those are used.
* For `run-benchmark`, metrics are harvested from the **official JSON report** written by GenAI Flow's benchmark mode
  and should be treated as the authoritative numbers.

<a name="vision-language-model-ask-vlm"></a>
## 7. Vision Language Model (ask-vlm)

The GenAI Flow repository also ships a **VLM submodule** (SmolVLM2-256M/500M) that answers natural-language questions
about images — this demo wires it to a USB camera so you can ask about the live scene from /IOTCONNECT.

### Install

The VLM submodule was fetched and installed in [section 3](#3-install-nxp-eiq-genai-flow) (`/root/vlm`). If you
skipped that step, run it now:

```bash
cd /root/vlm && ./install.sh
```

Connect a UVC USB webcam to the board's **USB A** port (circled in the
[quickstart's connector diagram](../README.md#3-hardware-setup)) and find its device node with `v4l2-ctl --list-devices` (e.g. a Logitech C920 typically
appears as `/dev/video52` on this image, among the many i.MX95 ISP nodes). Set `camera_device` in
`/opt/demo/genai-config.json` if yours differs, along with `vlm_model` (`smolvlm-256M` default, or `smolvlm-500M`)
and `vlm_precision` (`q8` default, or `fp32`) — or switch the vision model from the cloud at any time with the
`set-vlm` command (e.g. `set-vlm smolvlm-500M`), no SSH needed.

### Use

Send the `ask-vlm` command from /IOTCONNECT — with no argument it describes the scene; or ask something specific like
`Is there a person in the room?`. The app captures a fresh frame via GStreamer, runs the VLM (models download on
first use), and publishes `vlm_response` plus performance telemetry.

Measured on the FRDM-IMX95 CPU with SmolVLM2-256M q8 and a 1280×720 frame: **vision encode ~4.4 s, time to first
token ~4.9 s, decode ~9.5 tok/s** (see [MODELS.md](MODELS.md)).

## 8. Voice Assistant (voice-start)

The `voice-start` command turns the board into a fully offline voice assistant using GenAI Flow's complete pipeline:
**"Hey NXP"** wake-word detection (VIT) → speech-to-text (Moonshine) → LLM (Danube, CPU or Neutron NPU per
`set-backend`) → streaming text-to-speech (VITS), with every exchange published to /IOTCONNECT.

### Audio hardware

GenAI Flow auto-detects audio devices. On a FRDM-IMX95 with a USB webcam this means the webcam's microphone for
capture and the **MQS 3.5 mm jack** for TTS playback (circled in the
[quickstart's connector diagram](../README.md#3-hardware-setup)) — plug in headphones or a powered speaker to hear the replies
(or start with `voice-start text` for dashboard-only responses). A USB headset with echo cancellation (e.g. a
business/UC model) improves wake-word and transcription accuracy; override `capture_device` / `playback_device` in
`/opt/demo/genai-config.json` to select it (ALSA names from `arecord -l` / `aplay -l`, e.g. `sysdefault:CARD=H570e`).

### Using it

1. Send `voice-start` and wait for `voice_status` to reach `listening` (~1–3 minutes while models load; longer on the
   Neutron backend due to the NPU compile).
2. Say **"Hey NXP"**, pause until `voice_status` shows `capturing` (or you hear the earcon), then ask your question.
3. The answer streams out loud and lands in `voice_question` / `voice_response` / `voice_exchanges` telemetry.
4. The session re-arms for the next wake word; send `voice-stop` to end it.

> [!TIP]
> Speak the wake word, pause, *then* ask — running them together can put "Hey NXP" into the transcription itself.
> While a voice session is active, `ask-llm`, `ask-vlm`, and `run-benchmark` report busy.

### Tuning

* **Set the capture gain first (STT accuracy depends on it).** The microphone capture level is very low by default
  on this image — low enough that speech-to-text still *works*, but transcription accuracy jumps dramatically once
  the gain is raised (true for both the webcam mic and USB microphones). Turn it up with `alsamixer`:
  ```bash
  alsamixer                 # press F6, pick the capture card (your mic); F4 for Capture view;
                            # raise the Capture/Mic level with the Up arrow (aim high, ~80–100%)
  alsactl store            # persist the levels across reboots
  ```
  Or set it non-interactively, e.g. `amixer -c <card> sset 'Mic' 100%` (use `arecord -l` to find the card and
  `amixer -c <card> scontrols` for the exact control name). Re-run the [venue mic check](demo-flow.md#venue-mic-check-run-after-any-board-move-before-doors-open) — you want speech seconds at **2000+ RMS**.
* **Getting cut off mid-question?** GenAI Flow ends speech capture after only 200 ms of silence by default, which
  truncates questions to their first word or two. Raise it (800 ms works well) in
  `/root/eiq_genai_flow/adapters/stt/stt_adapter.py`:
  ```python
  vad_min_silence_duration_ms: int = 800
  ```
  Restart the voice session (`voice-stop` / `voice-start`) to apply.
* **Latency vs. accuracy**: `stt_model` in `/opt/demo/genai-config.json` selects the transcriber —
  `moonshine-tiny` (fastest, default), `moonshine-base`, or `whisper-small.en` (most accurate).

## 9. RAG: Ground Answers in Your Own Documentation (set-rag)

Small language models hallucinate facts. RAG (Retrieval-Augmented Generation) fixes that by retrieving relevant
passages from an on-device vector database and injecting them into the prompt — turning the board into an offline
**"ask the manual"** assistant. This demo ships a knowledge base about the FRDM-IMX95 itself
([rag-db/FRDM95_hand_made_chunks.json](rag-db/FRDM95_hand_made_chunks.json)), so the board can answer questions about
its own setup, commands, and measured performance with real numbers instead of inventions.

### Build the database (runs on the board — no PC tooling needed)

NXP's docs describe a PC-based flow (Docling PDF parsing + a GPU chunking model), but hand-made chunk files skip all
of that, and the embedding step runs fine on the i.MX95 itself (~30 chunks/sec):

```bash
# On the board:
cd /root/eiq_genai_flow/rag/src/data
mkdir -p medical-backup
mv chunked_files/Medical_*.json medical-backup/           # remove the sample medical content
cp rag_database.pkl medical-backup/                       # keep a backup
# copy FRDM95_hand_made_chunks.json (from this repo's rag-db/) into chunked_files/, then:
cd /root/eiq_genai_flow/rag/src
echo "User guide for the NXP FRDM i.MX 95 development board." | \
  python3 -m rag.preprocessing.generate_embeddings -f all
```

To use your own content, write a chunk file in the same JSON format — **one single-chunk group per passage**, as
in the shipped file — and rebuild; any product manual, datasheet, or procedure text works.

> [!WARNING]
> Do **not** put many chunks into one group: GenAI Flow's reranker scores a group by the *mean* embedding of all
> its chunks, so a multi-chunk group gets diluted and reliably loses to the single-chunk `garbage_model` entries —
> the classifier then rejects even perfectly on-topic questions with "I'm unable to assist you with this topic."

You can also manage the database **from the cloud**, no SSH needed: `rag-add <document URL> [name]` downloads a
document (upload it via IOTCONNECT to get a URL), chunks and embeds it on the board (progress in `rag_status` /
`rag_detail`); `rag-show <name>` publishes a preview of a document's chunks; `rag-remove <name>` deletes it.

### Calibrate the ambiguity threshold

GenAI Flow's query classifier rejects questions as "ambiguous" when retrieval similarity is below
`similarity_threshold` (default 0.65) in `/root/eiq_genai_flow/config.py`. With MiniLM embeddings and hand-made
chunks, correct matches typically score 0.31–0.45 (e.g. *"How do I expand the root filesystem?"* scores 0.31
against its own chunk), so lower it:

```python
similarity_threshold: float = 0.30
```

### Use it

Toggle grounding from /IOTCONNECT with `set-rag on` / `set-rag off` (reflected in the `llm_rag` telemetry
attribute). It applies to `ask-llm`, the voice assistant, and `run-benchmark`. Example, with RAG on:

> **ask-llm** `How do I expand the root filesystem?` →
> *"The stock FRDM i.MX 95 demo image only allocates about 11 GB of the 32 GB eMMC to the root filesystem. Expand it
> with: parted -s /dev/mmcblk0 resizepart 2 100% followed by resize2fs /dev/mmcblk0p2"* — verbatim from the docs.

## 10. Agent: LLM with Real Board Tools (ask-agent)

Ask the plain LLM *"what time is it?"* and it will confidently invent one. The agent fixes that with function
calling: the LLM only **chooses** a tool, the board **executes** it, and the answer is grounded in the tool's real
output — a complete plan → act → respond loop running on a small model at the edge.

| Tool | Real data source |
|---|---|
| `get_time` | board clock (NTP-synced) |
| `get_temperature` | SoC thermal zone |
| `get_memory` | /proc/meminfo + CPU load |
| `get_uptime` | /proc/uptime |
| `get_ip` | network stack |
| `get_usb` | lsusb - live USB device list |

### Use it

Send `ask-agent` with a request that needs live data, e.g. `what time is it`, `how warm is the chip`,
`how much memory is in use`. Telemetry shows the whole reasoning chain: `agent_tool` (which tool was picked),
`agent_tool_result` (the real data), `agent_response` (the grounded answer), and `agent_router` — `llm` when the
model chose the tool itself, `keyword-override` when the safety net overrode a bad pick, `keyword` when the
fallback matcher rescued an unparseable one.

The agent keeps one persistent LLM session alive (CPU backend), so the **first** request takes ~1 minute to load and
subsequent ones answer in seconds. The session stops itself after 60 idle minutes (configurable via
`agent_idle_timeout_s`), or immediately with `agent-stop`.

Beyond the local tools, the agent can also query your **/IOTCONNECT account itself** (fleet devices, health,
telemetry readback) through Avnet's [iotc-mcp-server](https://github.com/avnet-iotconnect/iotc-mcp-server) running
on the board. Install it on the board (both lines matter — see the note below):

```bash
python3 -m pip install --ignore-installed --no-deps idna==3.11   # whinlatter ships idna without pip metadata
python3 -m pip install iotconnect-mcp-server "mcp<2"             # the server is built against the 1.x MCP SDK
```

Start it with `iotc-mcp-server` (the demo expects it at `http://127.0.0.1:8000/mcp` — `mcp_url` in
`/opt/demo/genai-config.json`) and authenticate once with `iotconnect-cli configure` (the session token refreshes
automatically afterwards). Without it, the local board tools above still work — only the cloud-backed tools report
the server as unreachable.

> [!NOTE]
> Both workarounds were hit on a stock whinlatter board: a plain `pip install iotconnect-mcp-server` fails with
> *"Cannot uninstall idna 3.11 … no RECORD file"* (the image's `idna` lacks pip metadata — the first line fixes
> that), and without the `"mcp<2"` pin the resolver picks the MCP 2.x SDK, which removed the `fastmcp` module the
> server imports (`ModuleNotFoundError: mcp.server.fastmcp` at startup).

### Companion device: MCX predictive-maintenance (PdM)

Beyond the board-local tools above, the agent can **monitor and control a second device over /IOTCONNECT** through
the on-board MCP server — an **FRDM-MCXN947** running the
[eIQ predictive-maintenance vibration demo](https://github.com/avnet-iotconnect/iotc-zephyr-demos/tree/main/demos/eiq-pdm-vibration)
(NXP FXLS8974CF accelerometer + an on-Click balanced/unbalanced motor pair, classified on-device by an eIQ Time
Series Studio model). It's a natural pairing for a booth: the i.MX 95 queries the machine's health and injects
faults by voice, and the MCXN947 detects them.

| Tool | What it does |
|---|---|
| `get_vibration` | reads the MCX device's latest `vib.*` telemetry (motor state, RMS g, anomaly score) from /IOTCONNECT |
| `send_motor_command` | maps natural language to the PdM device's commands — `inject-fault` (spin the unbalanced motor), `inject-healthy`, `run-both`, `motor-stop`, `set-threshold`, `set-interval`, `reboot` |

Set the target device in `/opt/demo/genai-config.json` (`vibration_duid`, default `mclMCXvib`). Then, with the
agent warm: `ask-agent how's the motor` → reads the live state; `ask-agent inject a fault` → the unbalanced motor
spins and the MCX board reports `fault`. Requires the MCP server running and authenticated (see above) and the
companion device onboarded — see the [eIQ PdM demo](https://github.com/avnet-iotconnect/iotc-zephyr-demos/tree/main/demos/eiq-pdm-vibration).

### Test without the cloud

Both the agent and the plain LLM path can be exercised with no /IOTCONNECT connection:

```bash
cd /opt/demo
python3 app.py --test-agent what time is it
python3 app.py --test-llm what is an npu
```

## 11. Model Ladder: Bigger LLMs via llama.cpp (set-model)

Danube-500M is fast but shallow. [llama.cpp](https://github.com/ggml-org/llama.cpp) lets the same `ask-llm` command
run **larger open models** on the i.MX 95's CPU — trading speed for answer quality, and previewing what the Kinara
Ara-2 module will make fast. Any `.gguf` file dropped in `/opt/llama/models/` becomes a valid `set-model` target
(send an invalid `set-model` to get the list of available models in the failure message).

### One-time setup (on the board)

```bash
mkdir -p /opt/llama/models && cd /opt/llama
curl -sL https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/heads/master -o llama.tar.gz
tar -xzf llama.tar.gz && mv llama.cpp-master src
cd src && cmake -B build -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF -DGGML_NATIVE=ON
cmake --build build --target llama-cli llama-bench -j6      # ~15 min on the A55s

cd /opt/llama/models
curl -sL -O "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
curl -sL -O "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q8_0.gguf"
```

### Use it

From /IOTCONNECT: `set-model qwen2.5-1.5b-instruct-q4_k_m`, then `ask-llm` as usual — `llm_backend` telemetry
reports `cpu-llama.cpp`, and `llm_tps` / `llm_ttft` come from llama.cpp's own timing instrumentation. Switch back
anytime with `set-model danube-500M-q8`.

### Measured ladder (FRDM-IMX95, 6 threads)

| Model | Runtime | Load (s) | Tokens/sec | Answer quality (same question set) |
|---|---|---|---|---|
| danube-500M-q8 | GenAI Flow, CPU | 44 | 10.1 | Fluent but factually shaky (invented dates, "NPU analyzes the human brain") |
| danube-500M-q8 | GenAI Flow, Neutron NPU | 129 | **13.7** | Same model, faster path |
| danube-500M-q4 | GenAI Flow, Neutron NPU | 147 | **15.9** | Fastest measured; terser, lower-quality answers |
| qwen2.5-0.5b-instruct-q8_0 | llama.cpp, CPU | **5.6** | 12.9 | Noticeably better facts at Danube-NPU speed, with a 23× faster load |
| qwen2.5-1.5b-instruct-q4_k_m | llama.cpp, CPU | 7.1 | 5.7 | Best reasoning of the set — right decade and real details on niche questions |

Full matrix, methodology, and the VLM/STT tables: [MODELS.md](MODELS.md).

The takeaway for the Ara-2: the quality you want lives in the bigger rows, and today they cost tokens/sec. A
discrete NPU moves those rows up the speed column without giving up the quality.

## 12. Booth Dashboard and Live Camera

A ready-made /IOTCONNECT dashboard for demos and trade-show booths is included:
[FRDM_i.MX_95_GenAI_dashboard.json](FRDM_i.MX_95_GenAI_dashboard.json). It shows the board image, live gauges
(tokens/sec, SoC temperature, CPU), the latest LLM / VLM / voice / agent responses with the agent's full reasoning
chain, one-click Control widgets (RAG on/off, CPU/NPU backend, "Ask VLM", "Agent: what time is it"), a free-form
Device Command panel, and an embedded live camera view.

### Import

1. Make sure the `genaiflow` template has **all** attributes (including the `agent_*` set and `llm_rag`) and
   commands from [genai-flow-template.json](genai-flow-template.json).
2. In /IOTCONNECT select **Create Dashboard → Import**, choose the JSON file, and map it to the `genaiflow`
   template and your device.
3. Widgets can then be rearranged/resized to taste — re-export to save your layout.

### Live camera in the dashboard (Embedded widget)

`camera-server.py` (installed with this demo in `/opt/demo`) streams HTTPS MJPEG from the USB camera:

```bash
cd /opt/demo && nohup python3 camera-server.py > camera.log 2>&1 &
```

* Endpoints: `https://<board-ip>:8080/live` (MJPEG stream), `/snapshot` (single JPEG).
* Edit the dashboard's **Embedded** widget link to your board's IP.
* The certificate is self-signed: open `https://<board-ip>:8080` once in a browser tab and accept the warning,
  after which the embedded view renders.
* The server shares frames with `ask-vlm` (via `/tmp/camera-latest.jpg`), so vision commands keep working while
  streaming — no camera contention.

> [!TIP]
> For remote (off-LAN) streaming or recorded footage, the AWS KVS demos from the i.MX93 directory
> ([kvs-putmedia](../../nxp-frdm-imx-93/kvs-putmedia/README.md) /
> [kvs-webrtc](../../nxp-frdm-imx-93/kvs-webrtc/README.md)) can be adapted to this board and pair with the
> dashboard's Video Stream widget — that requires AWS KVS setup on your /IOTCONNECT account.

## 13. Going Further

* **Custom RAG content**: swap the FRDM95 chunks in section 9 for your own product documentation.
* **More agent tools**: add entries to `AGENT_TOOLS` in `app.py` — anything the board can read or do (GPIO, camera,
  scripts) becomes voice/cloud addressable.
* **Kinara Ara-2 / NXP Ara240**: NXP's discrete NPU module for accelerating larger LLMs at the edge — now wired in
  as the `ara2` backend (`set-backend ara2`), running Qwen2.5-7B on the module via the eIQ AAF Connector. See
  [Enabling the Ara240 backend](#enabling-the-kinara-ara-2--nxp-ara240-backend) for where to get the runtime and
  models, and [MODELS.md](MODELS.md) for measured performance.

## 14. Customize and Rebuild (Optional)

To modify the demo files before deploying:

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `nxp-frdm-imx-95/genai-flow-demo/src/` as needed.

3. Rebuild the package:
   ```bash
   cd nxp-frdm-imx-95/genai-flow-demo
   bash ./create-package.sh
   ```

4. Deliver the new package to the board:

   **Option A — Direct copy (scp):**
   ```bash
   # On host:
   scp package.tar.gz root@<board-ip>:/opt/demo/
   # On board:
   cd /opt/demo && tar -xzf package.tar.gz --overwrite && bash ./install.sh
   ```

   **Option B — OTA via /IOTCONNECT platform:**
   1. In the **Device** page, select **Firmware** on the bottom toolbar.
   2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `genaiflow`
      template, set version numbers (e.g., `0`, `0`), browse to `package.tar.gz`, and click **Save**.
   3. Back on the Firmware page, click the draft number under **Software Upgrades → Draft**.
   4. Click the publish icon (black square with arrow) under **Actions**.
   5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to
      **Devices**, select your device, and click **Update**.

   Shortly after, the running `app.py` will receive the package, decompress it, execute `install.sh`, and restart
   automatically.

## Resources

* [eIQ GenAI Flow Demonstrator (GitHub)](https://github.com/nxp-appcodehub/dm-eiq-genai-flow-demonstrator)
* [NXP eIQ GenAI Flow product page](https://www.nxp.com/design/design-center/software/embedded-software/eiq-genai-flow-conversational-ai-software-pipeline-on-edge-devices:GEN-AI-FLOW)
* [NXP i.MX 95 Applications Processor Family](https://www.nxp.com/products/i.MX95)
* [i.MX Machine Learning User's Guide (UG10166)](https://www.nxp.com/docs/en/user-guide/UG10166.pdf)
