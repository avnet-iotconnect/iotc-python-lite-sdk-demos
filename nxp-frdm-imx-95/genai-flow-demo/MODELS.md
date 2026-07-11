# AI Model Inventory — FRDM i.MX 95 GenAI Demo

Every model in the demo, its function, footprint, and measured performance. All performance figures were
**measured on a FRDM-IMX95** (BSP LF6.18.2, 6× Cortex-A55 @ ~1.8 GHz, eIQ Neutron NPU, 8 GB LPDDR4X) unless
marked as vendor reference. On-disk sizes are as installed on the board.

## Language models (text generation)

| Model | Params / quant | On disk | Runtime | Used by | Measured performance |
|---|---|---|---|---|---|
| **Danube-500M q8** | ~500 M, 8-bit (encrypted ONNX) | 496 MB | eIQ GenAI Flow / onnxruntime | `ask-llm`, voice assistant, RAG answers, agent (router + synthesis) | **CPU:** 10.9 tok/s, TTFT 0.67 s, load ~41 s · **Neutron NPU:** 13.9 tok/s (+27 %), TTFT 0.50 s, load ~130 s (per-launch NPU compile) · **Official benchmark (NPU + RAG):** 12.92 tok/s avg, TTFT 0.28 s, 23.6 % CPU |
| **Danube-500M q4** | ~500 M, 4-bit (encrypted ONNX) | 345 MB | eIQ GenAI Flow | `set-model danube-500M-q4` | Installed, not yet evaluated (expect faster/lighter, lower quality) |
| **Qwen2.5-0.5B-Instruct Q8_0** | 0.5 B, 8-bit GGUF | 645 MB | llama.cpp, CPU (6 threads) | `set-model` → `ask-llm` | **~14 tok/s**, load ~3 s — Danube-NPU speed on CPU alone, with noticeably better factuality (correct NPU definition, Everest 8848 m) |
| **Qwen2.5-1.5B-Instruct Q4_K_M** | 1.5 B, 4-bit GGUF | 1.1 GB | llama.cpp, CPU (6 threads) | `set-model` → `ask-llm` | **6.5 tok/s**, load ~10 s — best reasoning of the set (right decade + real details on niche questions) |

**The ladder takeaway:** answer quality rises with parameter count and today costs tokens/sec on CPU; the
Kinara Ara-2 module targets exactly the bigger rows.

## Vision language model (image understanding)

| Model | Params / quant | On disk | Runtime | Used by | Measured performance |
|---|---|---|---|---|---|
| **SmolVLM2-256M INT8** | 256 M, 8-bit ONNX (vision encoder 90 MB + decoder 132 MB + embeddings 28 MB) | ~250 MB | onnxruntime, CPU | `ask-vlm` (camera scene Q&A) | **Vision encode 3.6–4.5 s**, TTFT (vision + decoder) ~4.1–5.0 s, **decode 9.5–11 tok/s** — reliably identifies people, clothing, held objects, room features |
| SmolVLM2-500M (q8 / fp32) | 500 M | downloads on first use | onnxruntime, CPU | `vlm_model` config option | Not evaluated here. Vendor reference: same vision encoder (~3.3 s), decoder TTFT 0.81 s @ q8 |

## Speech-to-text (voice assistant transcription)

Selected with `set-stt`; applies at the next `voice-start`. All 8-bit encrypted ONNX, CPU.

| Model | On disk | Character | Evaluation |
|---|---|---|---|
| **moonshine-tiny** | ~40 MB | Fastest, least accurate | Evaluated: shortest beep-to-answer gap, but mishears at distance ("what is a cake made out of" → "Is it Kate made out of") |
| **moonshine-base** | 84 MB | The balance — **recommended default** | Evaluated: near-miss transcriptions still land the LLM on the right answer at arm's-length mic distance |
| **whisper-small.en** | 275 MB | Most accurate, slowest | Installed, not yet evaluated on this board |

Wake-word note: reliable detection needs speech at roughly **≥ 4000 RMS** at the mic (~arm's length on a webcam
mic); ~900 RMS at casual seating distance fails against a ~450 noise floor. See the mic check in
[demo-flow.md](demo-flow.md).

## Text-to-speech (spoken replies)

| Model | On disk | Runtime | Used by | Notes |
|---|---|---|---|---|
| **VITS streaming, English multi-speaker, 16 kHz quant** | 22 MB (quant; 145 MB fp variants also shipped) | onnxruntime, CPU | voice assistant (`-o tts`) | Streams audio as tokens generate; replies start speaking ~10–20 s after the question ends (whole-pipeline latency, not TTS-bound). Benchmark can report TTS real-time factor (`bench_tts_rtf`) |

## Wake word

| Model | Function | Notes |
|---|---|---|
| **NXP VIT (Voice Intent Technology), English** | Always-on "Hey NXP" detector | Small binary (`VIT_Model_en.bin`); runs continuously at ~5 % CPU during a voice session |

## Retrieval / embeddings (RAG)

| Model | Params | On disk | Function | Measured performance |
|---|---|---|---|---|
| **all-MiniLM-L6-v2** (ONNX) | ~22 M, 384-dim | 88 MB | Embeds the knowledge base and each query; retrieval, reranking, and query classification (in/out-of-domain) | Database build: **~30 chunks/s on the A55s** (25-chunk board KB in <1 min). Correct-match query similarity typically **0.35–0.45** with hand-made chunks — hence the 0.65→0.35 classifier threshold change (see README §9) |

## What runs where (at demo time)

| Engine | Model(s) resident | RAM while loaded |
|---|---|---|
| `ask-llm` / voice / RAG | Danube (or a Qwen GGUF via llama.cpp) | ~1.7–2.5 GB |
| Agent (persistent session) | Danube q8, CPU, RAG off | ~1.8 GB |
| `ask-vlm` | SmolVLM2-256M (per-request process) | ~1.7 GB transient |
| Voice session | Danube + Moonshine + VITS + VIT | ~2.5–4 GB (NPU backend adds CMA use) |

One AI operation runs at a time (busy-lock), but resident sessions (agent, voice) coexist in RAM — the 8 GB
board holds an active voice session plus the warm agent with headroom.
