# Dashboard tile icons

Flat line glyphs for the four /IOTCONNECT status tiles that report which engine is loaded. The icon is the
concept; the **value comes from telemetry**, so these never go stale when a model or backend changes.

| Icon | Tile | Telemetry attribute | Example values |
|---|---|---|---|
| `backend` (chip) | Backend | `llm_backend` | `cpu` · `neutron` · `cpu-llama.cpp` · `ara2` |
| `llm-model` (speech bubble) | LLM Model | `llm_model` | `danube-500M-q8` · `qwen2.5-1.5b-instruct-q4_k_m` · `Qwen2.5-7B-Instruct` |
| `vlm-model` (eye) | VLM Model | `vlm_model` | `smolvlm-256M (q8)` |
| `stt-model` (microphone) | STT Model | `voice_stt` | `moonshine-tiny` · `moonshine-base` · `whisper-small.en` |

These four cover the gap left by the `Backend` and `Model` **toggle** widgets, which are two-state controls and
cannot display `ara2` or a real model name — see the widget audit in [VIDEO-SCRIPT.md](../../VIDEO-SCRIPT.md).

## Files

| Pattern | Use |
|---|---|
| `<name>-64.png`, `-128.png`, `-256.png` | Slate `#243247` on transparent — for light tiles |
| `<name>-white-64.png`, `-128.png`, `-256.png` | White on transparent — for dark tiles |
| `<name>.svg` | Editable source, `stroke="currentColor"` — recolour or scale to anything |

All PNGs are RGBA with a transparent background, rendered from the SVG at 1024 px and Lanczos-downsampled, so
64 px stays sharp. Largest file is 17 KB.

Drawn on a 24×24 grid, 1.6 stroke, round caps and joins — matching stroke weight across all four so a row of
tiles reads as one set. To regenerate or restyle, edit the SVGs and re-render at 4× the target size.
