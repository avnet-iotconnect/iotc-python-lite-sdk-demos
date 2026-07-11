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
  and answered about by SmolVLM running on the board (see [Vision Language Model](#vision-language-model-ask-vlm)).
* **Run the official GenAI Flow benchmark** (`run-benchmark`) and publish its metrics (TTFT, tokens/sec, CPU/memory
  averages) to your dashboard.
* **Switch models and backends** (`set-model`, `set-backend`) to compare CPU vs. eIQ Neutron NPU performance.
* **Monitor the board** continuously (CPU %, memory, SoC temperature) while models are running.

### Execution backends

| Backend | Status | Notes |
|---|---|---|
| Cortex-A55 CPU (6 cores) | ✅ Supported | Default. Runs Danube-500M q8/q4 |
| eIQ Neutron NPU | ✅ Supported (experimental) | `set-backend neutron`; requires i.MX 95 **B0** silicon (SoC revision 2.0) and a Neutron memory pool in the device tree — see [Enabling the Neutron NPU](#enabling-the-neutron-npu) |
| Kinara Ara-2 discrete NPU module | 🔜 Planned | Will enable much larger LLMs at higher tokens/sec. This demo's `backend` config field is designed to add an `ara2` option once the module and runtime are available |

### Measured performance

Measured on a FRDM-IMX95 (BSP LF6.18.2, `danube-500M-q8`, identical 54-token prompt):

| Metric | CPU (6× Cortex-A55) | eIQ Neutron NPU |
|---|---|---|
| Tokens/sec | 10.9 | **13.9** (+27%) |
| Time to first token | 0.67 s | 0.50 s |
| Pipeline load time | ~41 s | ~132 s (includes NPU model compile) |

## 2. Requirements

* Completed [FRDM i.MX 95 quickstart](../README.md) (starter demo onboarded and working in `/opt/demo`)
* NXP Linux BSP **L6.12.49-2.2.0 or later** recommended (see the [flashing guide](../FLASHING.md) to update)
* At least **16 GB free storage** on the board for GenAI Flow and its models
* Internet access on the board (models are downloaded on first use)

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

The eIQ GenAI Flow demonstrator is delivered by NXP as a separate repository (models are encrypted binaries downloaded
on first use). Install it on the board first:

1. On your **host PC** (needs Git LFS):

   ```bash
   sudo apt update && sudo apt install git-lfs
   git lfs install
   git clone --single-branch -b release/v3.0 https://github.com/nxp-appcodehub/dm-eiq-genai-flow-demonstrator
   cd dm-eiq-genai-flow-demonstrator
   scp -r eiq_genai_flow root@<board-ip>:/root/
   ```

2. On the **board**:

   ```bash
   cd /root/eiq_genai_flow
   ./install.sh
   ```

3. (Optional) Sanity-check it standalone before wiring up /IOTCONNECT — keyboard in, text out:

   ```bash
   python3 eiq_genai_flow.py -i keyb -o text -m danube-500M-q8
   ```

> [!NOTE]
> If you install GenAI Flow somewhere other than `/root/eiq_genai_flow`, edit the `genai_dir` field in
> `/opt/demo/genai-config.json` after step 5 below.

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
wget -O package.tar.gz https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-95/genai-flow-demo/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

### Run

```bash
python3 app.py
```

> [!TIP]
> For hands-off starts (booth staff, colleagues), copy [board-readme.txt](board-readme.txt) to the board as
> `/root/readme.txt` — anyone can then `cat readme.txt` and paste the block it prints to start every demo
> service (app, camera server, MCP server) with a built-in status check.


## 6. Using the Demo

Once running, system telemetry streams to /IOTCONNECT every 10 seconds. Use the **Command** panel on your device page
to interact with the LLM:

| Command | Argument | What it does |
|---|---|---|
| `ask-llm` | prompt text, e.g. `What is the capital of France?` | Runs the prompt through the on-device LLM. The command is acknowledged immediately; the response arrives as `llm_response` telemetry along with `llm_ttft`, `llm_gen_time`, `llm_tps`, and `llm_token_count` |
| `ask-vlm` | *(optional)* question, e.g. `Is there a person in the room?` | Captures a frame from the USB camera and answers the question about it with SmolVLM. Response arrives as `vlm_response` telemetry with `vlm_vision_time`, `vlm_ttft`, and `vlm_tps`. Defaults to "Describe what you see in this image." |
| `ask-agent` | request needing live data, e.g. `what time is it` | Function calling: the LLM picks a real board tool (time, temperature, memory, uptime, IP), the board executes it, and the grounded answer plus the full reasoning chain arrive as `agent_*` telemetry. See [Agent](#10-agent-llm-with-real-board-tools-ask-agent) |
| `agent-start` | — | Pre-warms the agent session (~1 min) so the first question answers in seconds — send at booth open |
| `agent-stop` | — | Stops the agent’s persistent LLM session (it also auto-stops after 15 idle minutes) |
| `voice-start` | *(optional)* `tts` (default) or `text` | Starts the wake-word voice assistant ("Hey NXP" → speech-to-text → LLM → text-to-speech). Each exchange publishes `voice_question`, `voice_response`, and `voice_exchanges`; session state is in `voice_status` |
| `voice-stop` | — | Stops the voice assistant session |
| `set-stt` | `moonshine-tiny`, `moonshine-base`, or `whisper-small.en` | Selects the voice transcriber (speed vs. accuracy). Applies on the next `voice-start` |
| `run-benchmark` | *(optional)* extra CLI args, e.g. `-i vasr -o tts` | Runs GenAI Flow's official benchmark mode (`-r -b`) and publishes `bench_*` metrics. Defaults to keyboard/text mode so no audio hardware is needed |
| `set-model` | `danube-500M-q8`, `danube-500M-q4`, or any GGUF model name from `/opt/llama/models` (e.g. `qwen2.5-1.5b-instruct-q4_k_m`) | Selects the LLM used for subsequent commands. GGUF models run via llama.cpp on the CPU |
| `set-backend` | `cpu` or `neutron` | Toggles eIQ Neutron NPU acceleration (see requirements above) |
| `get-ip` | — | Returns the board's local IP address |
| `file-download` | package URL | Self-update with a new demo package |

> [!NOTE]
> The **first** `ask-llm` after boot takes noticeably longer while the model is loaded (and downloaded on first ever
> use) — watch `llm_load_time`. Subsequent prompts are faster. While a prompt or benchmark is running, `genai_status`
> reports `generating` / `benchmarking`.

<a name="enabling-the-neutron-npu"></a>
### Enabling the Neutron NPU

The stock FRDM-IMX95 demo image does **not** reserve the DMA memory pool the Neutron NPU needs for LLM inference
(`CmaTotal` shows only ~960 MB; NXP requires >3 GB), and unlike the i.MX 95 EVK images it ships no
`*-neutron.dtb`. You can build one on the board itself in about a minute using NXP's official overlay:

```bash
# On the board - create NXP's neutron memory overlay (4 GB pool at 0x100000000)
cat > /tmp/neutron.dtso << 'EOF'
/dts-v1/;
/plugin/;

&{/reserved-memory} {
	#address-cells = <2>;
	#size-cells = <2>;

	neutron_mem: neutron_memory@100000000 {
		compatible = "shared-dma-pool";
		reusable;
		reg = <0x1 0x00000000 0x1 0x00000000>;
	};
};

&neutron {
	memory-region = <&neutron_mem>;
};
EOF

cd /run/media/boot-mmcblk0p1
dtc -@ -I dts -O dtb -o /tmp/neutron.dtbo /tmp/neutron.dtso
cp imx95-15x15-frdm.dtb /root/imx95-15x15-frdm.dtb.orig            # keep a backup!
fdtoverlay -i /root/imx95-15x15-frdm.dtb.orig -o imx95-15x15-frdm.dtb /tmp/neutron.dtbo
sync && reboot
```

After the reboot, verify:

```bash
grep -i cma /proc/meminfo   # CmaTotal should now be ~5 GB (960 MB default + 4 GB Neutron pool)
ls /dev/neutron0            # NPU device present
```

To revert, copy `/root/imx95-15x15-frdm.dtb.orig` back over `imx95-15x15-frdm.dtb` and reboot.

> [!NOTE]
> The overlay is NXP's own `imx95-19x19-evk-neutron.dtso` from the
> [linux-imx kernel tree](https://github.com/nxp-imx/linux-imx/blob/lf-6.12.y/arch/arm64/boot/dts/freescale/imx95-19x19-evk-neutron.dtso),
> applied to the FRDM device tree. This demo requires 8 GB RAM boards (the pool reserves the 4 GB of DDR at
> `0x100000000`).

### Comparing CPU vs. NPU performance

A typical performance experiment from the /IOTCONNECT command panel:

1. `set-backend cpu` → `ask-llm Tell me about the i.MX 95 processor.` → note `llm_tps`
2. `set-backend neutron` → repeat the same prompt → compare `llm_tps` and `llm_ttft`

The Neutron backend requires the device tree change from [Enabling the Neutron NPU](#enabling-the-neutron-npu), and its
first response takes ~2 minutes longer while the model is compiled for the NPU (watch `llm_load_time`).

### Metrics notes

* For `ask-llm`, token counts (and therefore tokens/sec) are **estimated** from response length (~4 chars/token)
  unless GenAI Flow prints exact figures, in which case those are used.
* For `run-benchmark`, metrics are harvested from the **official JSON report** written by GenAI Flow's benchmark mode
  and should be treated as the authoritative numbers.

<a name="vision-language-model-ask-vlm"></a>
## 7. Vision Language Model (ask-vlm)

The GenAI Flow repository also ships a **VLM submodule** (SmolVLM-256M/500M) that answers natural-language questions
about images — this demo wires it to a USB camera so you can ask about the live scene from /IOTCONNECT.

### Install

The `vlm` directory sits next to `eiq_genai_flow` in the NXP repository you cloned in section 3:

```bash
# On your host PC:
scp -r dm-eiq-genai-flow-demonstrator/vlm root@<board-ip>:/root/
# On the board:
cd /root/vlm && ./install.sh
```

Connect a UVC USB webcam and find its device node with `v4l2-ctl --list-devices` (e.g. a Logitech C920 typically
appears as `/dev/video52` on this image, among the many i.MX95 ISP nodes). Set `camera_device` in
`/opt/demo/genai-config.json` if yours differs, along with `vlm_model` (`smolvlm-256M` default, or `smolvlm-500M`)
and `vlm_precision` (`q8` default, or `fp32`).

### Use

Send the `ask-vlm` command from /IOTCONNECT — with no argument it describes the scene; or ask something specific like
`Is there a person in the room?`. The app captures a fresh frame via GStreamer, runs the VLM (models download on
first use), and publishes `vlm_response` plus performance telemetry.

Measured on the FRDM-IMX95 CPU with SmolVLM-256M q8 and a 1280×720 frame: **vision encode ~3.6 s, time to first
token ~4.1 s, decode ~10–11 tok/s**.

## 8. Voice Assistant (voice-start)

The `voice-start` command turns the board into a fully offline voice assistant using GenAI Flow's complete pipeline:
**"Hey NXP"** wake-word detection (VIT) → speech-to-text (Moonshine) → LLM (Danube, CPU or Neutron NPU per
`set-backend`) → streaming text-to-speech (VITS), with every exchange published to /IOTCONNECT.

### Audio hardware

GenAI Flow auto-detects audio devices. On a FRDM-IMX95 with a USB webcam this means the webcam's microphone for
capture and the **MQS 3.5 mm jack** for TTS playback — plug in headphones or a powered speaker to hear the replies
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

To use your own content, write a chunk file in the same JSON format (groups of short, self-contained factual
passages) and rebuild — any product manual, datasheet, or procedure text works.

### Calibrate the ambiguity threshold

GenAI Flow's query classifier rejects questions as "ambiguous" when retrieval similarity is below
`similarity_threshold` (default 0.65) in `/root/eiq_genai_flow/config.py`. With MiniLM embeddings and hand-made
chunks, correct matches typically score 0.35–0.45, so lower it:

```python
similarity_threshold: float = 0.35
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
model chose the tool itself, `keyword` when the fallback matcher rescued an unparseable pick.

The agent keeps one persistent LLM session alive (CPU backend), so the **first** request takes ~1 minute to load and
subsequent ones answer in seconds. The session stops itself after 15 idle minutes (configurable via
`agent_idle_timeout_s`), or immediately with `agent-stop`.

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

| Model | Runtime | Tokens/sec | Answer quality (same question set) |
|---|---|---|---|
| danube-500M-q8 | GenAI Flow, CPU | 10.9 | Fluent but factually shaky (invented dates, "NPU analyzes the human brain") |
| danube-500M-q8 | GenAI Flow, Neutron NPU | **13.9** | Same model, fastest path today |
| qwen2.5-0.5b-instruct-q8_0 | llama.cpp, CPU | 13.9 | Noticeably better facts (correct NPU definition, Everest at 8848 m) at Danube-NPU speed |
| qwen2.5-1.5b-instruct-q4_k_m | llama.cpp, CPU | 6.5 | Best reasoning of the set — right decade and real details on niche questions — at half the speed |

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
* **Kinara Ara-2**: NXP's discrete NPU module for accelerating larger LLMs at the edge. Support will be added to this
  demo when the module is available — the config's `backend` field and `set-backend` command are the intended
  extension point, and the llama.cpp model ladder (section 11) shows exactly which models it will accelerate.

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
