# AI Model Inventory — FRDM i.MX 95 GenAI Demo

Every model in the demo, its function, footprint, and measured performance. **All figures were measured on a
FRDM-IMX95** (BSP LF6.18.2, 6× Cortex-A55, eIQ Neutron NPU, 8 GB LPDDR4X) in a single automated benchmark
suite for consistency: identical prompt/image/speech set per category, with the /IOTCONNECT app and camera
server running (honest demo conditions). **Load time is always a separate column** — performance numbers
(TTFT, tokens/sec, transcription time) never include model loading.

## Language models (text generation)

Same prompt for all six configurations. TTFT = time from prompt to first token, after the model is loaded.

| Model | Quant | On disk | Runtime / backend | **Load (s)** | TTFT (s) | **tok/s** | Notes |
|---|---|---|---|---|---|---|---|
| Danube-500M | q8 | 496 MB | GenAI Flow, CPU | 44 | 0.74 | 10.1 | The demo default — best Danube answer quality |
| Danube-500M | q8 | 496 MB | GenAI Flow, **Neutron NPU** | 129 | 0.48 | **13.7** | +35% over q8-CPU; load includes per-launch NPU compile |
| Danube-500M | q4 | 345 MB | GenAI Flow, CPU | 39 | 0.51 | 14.6 | Faster than q8-NPU on CPU alone; decent open-chat answers, but **fails RAG** (reproducibly returns canned refusals instead of quoting retrieved text) |
| Danube-500M | q4 | 345 MB | GenAI Flow, **Neutron NPU** | 147 | **0.31** | **15.9** | Fastest Danube config measured |
| Qwen2.5-0.5B-Instruct | Q8_0 | 645 MB | llama.cpp, CPU (6 threads) | **5.6** | **0.13** | 12.9 | Danube-NPU-class speed with notably better factuality — and a 23× faster cold start |
| Qwen2.5-1.5B-Instruct | Q4_K_M | 1.1 GB | llama.cpp, CPU (6 threads) | 7.1 | 0.83 | 5.7 | Best reasoning of the set; the quality-for-speed trade the Ara-2 will erase |

**Ladder takeaways:** quantization buys speed at answer-quality cost (q4 beats q8 everywhere on tok/s — but q4 cannot do grounded RAG answers, which is why q8 stays the demo default);
the NPU adds ~35% to whichever Danube quant it runs; llama.cpp's near-instant loads make the Qwens the
responsive choice despite CPU-only execution; and parameter count — not tok/s — is what buys reasoning. (Threading: Danube/onnxruntime uses the default
intra-op pool across all 6 cores; the Qwen runs are pinned to 6 threads — see the runtimes section below.)

## The two LLM runtimes

The language models run on two very different engines — most of the table above is explained by this split:

| | **eIQ GenAI Flow** (NXP) | **llama.cpp** (open source) |
|---|---|---|
| Model format | Encrypted ONNX, delivered by NXP (Danube only) | GGUF — any open model from Hugging Face |
| Execution engine | onnxruntime: CPU provider, or the **Neutron NPU** execution provider (i.MX 95 B0) | GGML CPU backend with Arm NEON |
| CPU threads | Not pinned — onnxruntime's default intra-op pool, all 6 Cortex-A55 cores available | Explicitly **6 threads** (`llama_threads` in `genai-config.json`) |
| Load behavior | Spawns a full pipeline process per session: **39–44 s** CPU, **129–147 s** NPU (the model is compiled for the NPU on every launch) | Memory-maps the GGUF: **5.6–7.1 s** cold start |
| NPU access | ✅ (this is the only path to the Neutron NPU) | ❌ — CPU only on this board |
| What it brings | The whole conversational stack: RAG, wake word, STT, TTS, benchmark mode, query classification | Bare, fast LLM inference |
| Used by | `ask-llm` (Danube), voice assistant, RAG, `run-benchmark`, the agent's session | `ask-llm` when a GGUF is selected via `set-model` |

The practical reading: **GenAI Flow is the pipeline, llama.cpp is the escape hatch.** GenAI Flow buys NPU
acceleration and every voice/RAG feature at the cost of heavyweight session startup and an NXP-only model list;
llama.cpp trades all the pipeline features for open model choice and near-instant loads. The demo uses both on
purpose — and the `set-model` command is the seam between them.

## Vision language models (image understanding)

Same image and question for both. Vision = image encoding; TTFT = vision + decoder to first token.

| Model | Quant | On disk | **Load (s)** | Vision (s) | TTFT (s) | **Decode tok/s** | Notes |
|---|---|---|---|---|---|---|---|
| SmolVLM2-256M | INT8 | ~250 MB | 43 | 4.41 | 4.94 | **9.5** | Demo default (`vlm_model` config) |
| SmolVLM2-500M | INT8 | ~460 MB | 81* | 4.45 | 5.40 | 5.5 | Same vision encoder (identical vision time); richer descriptions at half the decode speed. *First-run load includes model export |

## Speech-to-text (voice assistant transcription)

Measured by NXP's official benchmark: identical synthesized speech per model, word-error-rate scored against
the known transcript. Selected with `set-stt`; applies at the next `voice-start`.

| Model | On disk | **Load (s)** | Avg transcription (s) | WER (clean speech) | Notes |
|---|---|---|---|---|---|
| moonshine-tiny | ~40 MB | 28.5 | **3.85** | 1.06 % | Fastest. Clean-speech WER flatters it — its weakness is noisy/distant mic audio |
| moonshine-base | 84 MB | 29.9 | 4.21 | 1.59 % | **Recommended default** — the clean-set WER gap vs tiny is noise; base wins in real room acoustics |
| whisper-small.en | 275 MB | 35.8 | 5.40 | **0.00 %** | Perfect on the clean set for +1.2 s per utterance — the choice when accuracy is everything |

Wake-word note: reliable "Hey NXP" detection needs speech at roughly **≥ 4000 RMS** at the mic (~arm's length
on a webcam mic); ~900 RMS at casual seating distance fails against a ~450 noise floor. See the mic check in
[demo-flow.md](demo-flow.md).

## Text-to-speech (spoken replies)

| Model | On disk | Runtime | Used by | Notes |
|---|---|---|---|---|
| **VITS streaming, English multi-speaker, 16 kHz quant** | 22 MB (quant; 145 MB fp variants also shipped) | onnxruntime, CPU | voice assistant (`-o tts`) | Streams audio as tokens generate; replies start speaking ~10–20 s after the question ends (whole-pipeline latency, not TTS-bound) |

## Wake word

| Model | Function | Notes |
|---|---|---|
| **NXP VIT (Voice Intent Technology), English** | Always-on "Hey NXP" detector | Small binary (`VIT_Model_en.bin`); ~5 % CPU continuously during a voice session |

## Retrieval / embeddings (RAG)

| Model | Params | On disk | Function | Measured performance |
|---|---|---|---|---|
| **all-MiniLM-L6-v2** (ONNX) | ~22 M, 384-dim | 88 MB | Embeds the knowledge base and queries; retrieval, reranking, and in/out-of-domain classification | Database build: **~30 chunks/s on the A55s** (25-chunk board KB in <1 min). Correct-match query similarity typically **0.35–0.45** with hand-made chunks — hence the 0.65→0.35 classifier threshold change (README §9) |

## Board resources: what fits on a FRDM-IMX95

The board that runs all of the above (measured with the full demo kit installed):

| Resource | Total | Notes |
|---|---|---|
| **RAM** | 8 GB LPDDR4X (~7.7 GB usable) | Shared by Linux, the demo services, and every loaded model |
| **CMA / NPU pool** | ~5.1 GB (960 MB stock + 4 GB Neutron pool) | The 4 GB pool comes from the device-tree overlay (README §6); Neutron LLM inference consumes ~2.5 GB of it while loaded |
| **eMMC storage** | 32 GB (28 GB rootfs after expansion) | Stock image ships with only an 11 GB partition — expansion is step one (README §2) |

### Disk budget (as installed, measured)

| Component | On disk |
|---|---|
| NXP Linux BSP + system | ~6 GB |
| eIQ GenAI Flow (Danube q8+q4, 3× STT, TTS, wake word, RAG + MiniLM) | 1.6 GB |
| Python AI stack (torch, transformers, onnxruntime, MCP) | 1.6 GB |
| llama.cpp build + Qwen 0.5B & 1.5B GGUFs | 2.0 GB |
| SmolVLM (256M + 500M) | 0.7 GB |
| Demo app, camera server, RAG database, certs | 13 MB |
| **Free for more models** | **~16 GB** |

Headroom in practice: a Llama-3.1-8B Q4 GGUF is ~4.7 GB — three more models of that class fit on disk today
(running them fast is the Ara-2's job, below).

### RAM budget (what can be resident together)

| Combination | Approx. RAM | Fits? |
|---|---|---|
| System + demo services (app, camera, MCP) | ~1 GB | baseline |
| + warm agent session (Danube q8, CPU) | ~2.8 GB | ✅ |
| + active voice session (Danube + Moonshine + VITS + VIT) | ~5.3–6.8 GB | ✅ — the normal full-demo state |
| + an `ask-vlm` (transient ~1.7 GB) on top of the above | ~7–8 GB | ⚠️ tight — works, but this is the ceiling |
| Two Danube NPU sessions simultaneously | — | ❌ CMA contention; the busy-lock exists partly for this |

## What runs where (at demo time)

| Engine | Model(s) resident | RAM while loaded |
|---|---|---|
| `ask-llm` / voice / RAG | Danube (or a Qwen GGUF via llama.cpp) | ~1.7–2.5 GB |
| Agent (persistent session) | Danube q8, CPU, RAG off | ~1.8 GB |
| `ask-vlm` | SmolVLM2 (per-request process) | ~1.7 GB transient |
| Voice session | Danube + Moonshine + VITS + VIT | ~2.5–4 GB (NPU backend adds CMA use) |

One AI operation runs at a time (busy-lock), but resident sessions (agent, voice) coexist in RAM — the 8 GB
board holds an active voice session plus the warm agent with headroom.

## The Kinara Ara-2 plan: where this demo goes next

The Ara-2 is NXP's (Kinara) discrete edge NPU module — ~40 TOPS INT8, delivered as an M.2 card, purpose-built
for generative AI. This demo was architected for it from day one: the `backend` config field and `set-backend`
command are the drop-in point (`set-backend ara2`), and every command — `ask-llm`, the voice assistant, the
agent — keeps working unchanged, just faster and on bigger models.

**Everything below is projection, not measurement** — this table gets replaced with benchmark-suite numbers
the day the module arrives (the suite in `/root/bench_suite.py` re-runs the whole matrix in one command).

### Where we expect improvement (same models, same demo)

| Today's pain point | Measured today | Expected with Ara-2 |
|---|---|---|
| Qwen-1.5B reasoning is slow on CPU | 5.7 tok/s | Interactive speeds (~15–25 tok/s class) — the quality/speed trade disappears |
| NPU model compile on every launch | 129–147 s load | Precompiled model artifacts — llama.cpp-class load times on accelerated models |
| Vision encode dominates `ask-vlm` | 4.4 s | Sub-second-class encode; near-instant scene answers |
| CPU carries everything | 6 cores shared by LLM + STT + TTS + services | LLM/VLM offloaded — A55s free for audio, camera, and cloud |

### What becomes possible (new models, new functions)

* **8B-class LLMs on the board** — Llama-3.1-8B / Qwen-7B Q4 fit on disk today (~16 GB free); Ara-2 makes them
  *usable*. That means an agent that reliably routes tools and fills arguments without the keyword safety net,
  RAG synthesis that paraphrases instead of parroting, and genuinely conversational voice.
* **Bigger vision models** — 2B-class VLMs for fine-grained scene understanding (reading labels, counting
  objects, describing defects) instead of one-line captions.
* **Concurrent engines** — LLM on Ara-2, vision on the on-chip Neutron, speech on CPU: the one-AI-at-a-time
  busy-lock could relax into a true multi-model pipeline (watch the camera *while* holding a voice
  conversation).
* **The booth narrative completes** — the model ladder (§ language models) stops being a trade-off chart and
  becomes a before/after: same board, same demo, add the module, the smart models move to the fast column.
