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
| Danube-500M | q4 | 345 MB | GenAI Flow, CPU | 39 | 0.51 | 14.6 | Faster than q8-NPU on CPU alone; terser, lower-quality answers |
| Danube-500M | q4 | 345 MB | GenAI Flow, **Neutron NPU** | 147 | **0.31** | **15.9** | Fastest Danube config measured |
| Qwen2.5-0.5B-Instruct | Q8_0 | 645 MB | llama.cpp, CPU (6 threads) | **5.6** | **0.13** | 12.9 | Danube-NPU-class speed with notably better factuality — and a 23× faster cold start |
| Qwen2.5-1.5B-Instruct | Q4_K_M | 1.1 GB | llama.cpp, CPU (6 threads) | 7.1 | 0.83 | 5.7 | Best reasoning of the set; the quality-for-speed trade the Ara-2 will erase |

**Ladder takeaways:** quantization buys speed at answer-quality cost (q4 beats q8 everywhere on tok/s);
the NPU adds ~35% to whichever Danube quant it runs; llama.cpp's near-instant loads make the Qwens the
responsive choice despite CPU-only execution; and parameter count — not tok/s — is what buys reasoning.

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

## What runs where (at demo time)

| Engine | Model(s) resident | RAM while loaded |
|---|---|---|
| `ask-llm` / voice / RAG | Danube (or a Qwen GGUF via llama.cpp) | ~1.7–2.5 GB |
| Agent (persistent session) | Danube q8, CPU, RAG off | ~1.8 GB |
| `ask-vlm` | SmolVLM2 (per-request process) | ~1.7 GB transient |
| Voice session | Danube + Moonshine + VITS + VIT | ~2.5–4 GB (NPU backend adds CMA use) |

One AI operation runs at a time (busy-lock), but resident sessions (agent, voice) coexist in RAM — the 8 GB
board holds an active voice session plus the warm agent with headroom.
