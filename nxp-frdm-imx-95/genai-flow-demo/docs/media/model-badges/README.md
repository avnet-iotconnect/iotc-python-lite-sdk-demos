# Model-name badges (transformation widget)

One image per **attribute value**, for /IOTCONNECT transformation widgets that swap an image in place of a text
box. Four sets — `llm_model`, `vlm_model`, `voice_stt`, `llm_backend` — plus two shared fallback states.

Each badge carries the model name, a spec line, and a family accent bar. Every number on them is taken from
[MODELS.md](../../MODELS.md) — nothing is invented, and no live measurement is baked in (tokens/sec stays on the
gauge, where it belongs).

## Mapping: telemetry value → file

Map the **exact** attribute value, including case, spaces and parentheses. The `vlm_model` values are built as
`"<model> (<precision>)"` ([app.py:170](../../src/app.py#L170)), so they contain a space and brackets that the
filename drops.

### `llm_model`

| Attribute value | File stem |
|---|---|
| `danube-500M-q8` | `llm/danube-500M-q8` |
| `danube-500M-q4` | `llm/danube-500M-q4` |
| `qwen2.5-0.5b-instruct-q8_0` | `llm/qwen2.5-0.5b-instruct-q8_0` |
| `qwen2.5-1.5b-instruct-q4_k_m` | `llm/qwen2.5-1.5b-instruct-q4_k_m` |
| `Qwen2.5-7B-Instruct` | `llm/Qwen2.5-7B-Instruct` |
| `Qwen2.5-Coder-1.5B` | `llm/Qwen2.5-Coder-1.5B` |
| `Qwen25C15B` | `llm/Qwen25C15B` |

### `vlm_model`

| Attribute value | File stem |
|---|---|
| `smolvlm-256M (q8)` | `vlm/smolvlm-256M-q8` |
| `smolvlm-500M (q8)` | `vlm/smolvlm-500M-q8` |
| `smolvlm-256M (fp32)` | `vlm/smolvlm-256M-fp32` |
| `smolvlm-500M (fp32)` | `vlm/smolvlm-500M-fp32` |

### `voice_stt`

| Attribute value | File stem |
|---|---|
| `moonshine-tiny` | `stt/moonshine-tiny` |
| `moonshine-base` | `stt/moonshine-base` |
| `whisper-small.en` | `stt/whisper-small.en` |

### `llm_backend`

These are the only four values the app can publish (`app.py` lines [391](../../src/app.py#L391),
[457](../../src/app.py#L457), and `config["backend"]`). Note the file stem for the llama.cpp one drops the dot.

| Attribute value | File stem | Shows |
|---|---|---|
| `cpu` | `backend/cpu` | CPU — 6× Arm Cortex-A55 · eIQ GenAI Flow |
| `cpu-llama.cpp` | `backend/cpu-llama-cpp` | CPU · llama.cpp — 6× Arm Cortex-A55 · GGUF runtime |
| `neutron` | `backend/neutron` | eIQ Neutron NPU — on-chip NPU · i.MX 95 |
| `ara2` | `backend/ara2` | Kinara Ara-2 — Ara240 M.2 module · discrete NPU |

### Fallback states (use on any of the four attributes)

| When | File stem | Shows |
|---|---|---|
| Value is empty / no model loaded | `fallback/not-loaded` | **No model loaded** — engine idle |
| Value doesn't match any badge above | `fallback/other-model` | **Custom model** — value not in the badge set |

Both are drawn muted — grey name *and* grey accent bar — so they read as an absence rather than as another
model. Set `other-model` as the widget's default/unmatched image: a model pushed from IOTCONNECT arrives with an
arbitrary `Code` as its `llm_model` value, and without a default the widget renders nothing at all.

## Files

Every stem exists in four forms:

| Suffix | Size | Use |
|---|---|---|
| `-512.png` | 512×128 | Light tiles. Slate `#243247` name, grey spec |
| `-256.png` | 256×64 | Light tiles, small slot |
| `-white-512.png` | 512×128 | Dark tiles. White name, light-grey spec |
| `-white-256.png` | 256×64 | Dark tiles, small slot |

All RGBA with transparent backgrounds and a 4:1 aspect, rendered natively at each size (not upscaled), so the
256 px set stays sharp rather than soft. Each file is 3–9 KB.

## Accent colours

| Family | Colour | Models | Matching backend |
|---|---|---|---|
| Danube (eIQ GenAI Flow) | `#1F9D55` green | `danube-500M-q8/q4` | `neutron` |
| Qwen on CPU (llama.cpp) | `#2B6CB0` blue | `qwen2.5-0.5b…`, `qwen2.5-1.5b…` | `cpu-llama.cpp` |
| Kinara Ara-2 module | `#6B46C1` violet | `Qwen2.5-7B-Instruct`, `Qwen2.5-Coder-1.5B`, `Qwen25C15B` | `ara2` |
| SmolVLM | `#DD6B20` orange | all `vlm_model` values | — |
| Moonshine | `#805AD5` purple | `moonshine-tiny/base` | — |
| Whisper | `#2C7A7B` teal | `whisper-small.en` | — |
| Plain CPU | `#4A5568` slate | — | `cpu` |
| Empty / unknown | `#94A3B8` muted | `fallback/*` | — |

Qwen models split across **blue** and **violet** on purpose: the same family runs in two very different places,
and on an Ara240 board that distinction is the story. A glance at the badge colour tells you whether inference is
on the CPU or on the module.

The backend accents mirror the model accents (right-hand column above), so the **Model** tile and the **Backend**
tile colour-match on screen: green Danube next to green Neutron, violet Qwen-7B next to violet Ara-2. When the
backend changes mid-demo, both tiles change colour together — which is exactly the moment §3.6 and §3.7 of the
video script are built around.

## Adding a value

If you push a new model from IOTCONNECT, its `Code` becomes the `llm_model` value and needs a badge. Add a row to
`BADGES["llm"]` in [make-badges.py](make-badges.py) and re-run it — see the note in
[VIDEO-SCRIPT.md §1.6](../../VIDEO-SCRIPT.md). Until you do, `fallback/other-model` covers it, which is why it
should be the widget's default image.
