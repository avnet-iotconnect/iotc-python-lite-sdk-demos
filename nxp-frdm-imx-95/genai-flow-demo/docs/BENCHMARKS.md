# LLM Benchmark: one prompt, every backend and model

Measured **2026-07-28** on a FRDM i.MX 95 (8 GB LPDDR5) with a Kinara Ara-2 / NXP **Ara240** discrete NPU
(M.2, rt-sdk-ara2 2.0.4, eIQ AAF Connector on `:8100`). Every combination ran the **same prompt** through the
demo's real `ask-llm` code paths (`run_llm_prompt` in [src/app.py](../src/app.py)), one at a time, with CPU and
memory sampled once per second during each run. Responses below are **verbatim model output** — unedited.

> **Prompt:** `What color is an apple?`

Reproduce with [src/bench_llms.py](../src/bench_llms.py) (run on the board:
`python3 /tmp/bench.py`, results land in `/tmp/bench_results.json`) — or interactively from a browser with
[src/bench_server.py](../src/bench_server.py): it serves a shootout UI on `http://<board-ip>:8090` where you
type any prompt, tick the backend/model combinations to compare, and watch the same metrics and verbatim
responses stream in as each run completes. Install it as the `genai-bench` systemd service (same pattern as
`genai-camera`: `WorkingDirectory=/opt/demo`, `ExecStart=/usr/bin/python3 -u /opt/demo/bench_server.py`).

## Results

| Backend / Model | Load (s) | TTFT (s) | Gen (s) | Tok/s | Tokens | Wall (s) | CPU avg (%) | CPU peak (%) | Peak mem (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ara240 / Qwen2.5-7B-Instruct | 0.0 | 2.21 | 12.37 | 6.99 | 71 | 14.1 | 12.5 | 22.3 | 1116.2 |
| Ara240 / Qwen25C15B (Qwen2.5-1.5B) | 0.0 | 0.52 | 0.74 | 27.29 | 6 | 2.4 | 19.0 | 22.7 | 1116.6 |
| CPU (GenAI Flow) / danube-500M-q8 | 50.18 | 0.55 | 2.90 | 8.94 | 21 | 54.7 | 24.3 | 64.3 | 2828.5 |
| CPU (GenAI Flow) / danube-500M-q4 | 41.83 | 0.50 | 1.13 | 14.29 | 9 | 44.6 | 23.1 | 52.7 | 2233.6 |
| Neutron NPU (GenAI Flow) / danube-500M-q8 | 129.08 | 0.31 | 1.91 | 13.13 | 21 | 132.6 | 22.8 | 29.2 | 4521.2 |
| Neutron NPU (GenAI Flow) / danube-500M-q4 | 148.69 | 0.29 | 0.79 | 16.00 | 8 | 151.2 | 22.9 | 29.1 | 4212.5 |
| CPU (llama.cpp) / qwen2.5-0.5b-instruct-q8_0 | 7.18 | 0.09 | 7.44 | 12.10 | 90 | 16.4 | 45.4 | 75.3 | 2103.3 |
| CPU (llama.cpp) / qwen2.5-1.5b-instruct-q4_k_m | 15.17 | 0.52 | 4.34 | 5.30 | 23 | 21.7 | 45.5 | 89.0 | 3041.6 |

Notes on the columns:

- **Load** — model/pipeline initialization paid on this request. The Ara240 models stay resident in the AAF
  connector, so their load is 0 on every request; Danube pays a fresh GenAI Flow load here (the demo's warm
  session makes follow-up prompts skip it); Neutron's load includes NPU compilation.
- **Wall** — total wall-clock for the request end to end, as a booth visitor would experience it cold.
- **CPU / Peak mem** — sampled from `/proc/stat` and `/proc/meminfo` at 1 Hz while the request ran. Idle
  baseline before each run was ~1090–1120 MB used.

## The actual responses (verbatim)

### Ara240 / Qwen2.5-7B-Instruct

> Apples can come in various colors, but the most common ones are red, green, and yellow. Some varieties can
> also be a mix of these colors. There are also rare varieties that can be pink, orange, or even purple. The
> color of an apple can depend on the variety and its stage of ripeness.

### Ara240 / Qwen25C15B (pushed via IOTCONNECT model push)

> An apple is typically red.

### CPU (GenAI Flow) / danube-500M-q8

> An apple is a fruit that is typically red, round, and has a soft, juicy texture.

### CPU (GenAI Flow) / danube-500M-q4

> An apple is typically a bright red color.

### Neutron NPU (GenAI Flow) / danube-500M-q8

> An apple is a fruit that is typically red, round, and has a soft, juicy texture.

### Neutron NPU (GenAI Flow) / danube-500M-q4

> An apple is a bright red color.

### CPU (llama.cpp) / qwen2.5-0.5b-instruct-q8_0

> An apple is generally red in color. In many cultures, red is associated with fertility and good luck, so you
> might see red apples hanging on a tree or in a basket. However, it's important to note that apples can come in
> a variety of colors, including yellow, orange, pink, green, and purple, and there are also white, black, and
> other colors of apples available.

### CPU (llama.cpp) / qwen2.5-1.5b-instruct-q4_k_m

> An apple is typically green. However, when it is ripe and ready to eat, it turns red or yellow.

## Reading the results

- **Ara240** serves the largest model on the board (7B — 14× Danube's parameter count) with zero load time,
  the lowest CPU use (the NPU does the work), and essentially no host-RAM cost (~27 MB delta vs. 1.1–3.4 GB for
  the CPU paths). It is also home to the fastest configuration measured (the 1.5B at 27.3 tok/s, 2.4 s wall).
- **Neutron** delivers the best TTFT once running (0.29–0.31 s) but pays a 2–2.5 min compile/load and the
  highest memory (4.2–4.5 GB).
- **Response quality tracks model size.** Only the 7B covers red/green/yellow, mixes, and ripeness. The small
  CPU models answer "red" with varying confidence; the 0.5B rambles into folklore and invents white/black
  apples; the 1.5B leads with "green."
- Token counts are estimated at ~4 chars/token on paths that don't report an exact count, so tok/s across
  engines is comparable but approximate.

See [MODELS.md](../MODELS.md) for the full model catalog and
[docs/MODEL-PUSH.md](MODEL-PUSH.md) for how Qwen25C15B was deployed from the IOTCONNECT console.
