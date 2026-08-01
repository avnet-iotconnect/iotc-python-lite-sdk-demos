# "Ask the Camera" — CLIP Vision on Hailo-8 Quickstart

Cloud-reprogrammable AI vision on a Raspberry Pi 5 with the Hailo-8 M.2 AI
accelerator, connected to Avnet /IOTCONNECT: prompt commands down, live
similarity telemetry up, and embeddable live pages served from the board.

## 1. Introduction

The CLIP vision-language model runs on the Hailo-8 (image embeddings on the
NPU, text embeddings via the NPU text encoder) and scores the live camera
feed against plain-English prompts sent from the /IOTCONNECT dashboard —
*"a person waving"*, *"a red toolbox"* — with no retraining and no
redeployment. Scores are **softmax probabilities across the loaded prompts
(0–1)** — a clear match typically reads 0.9+, and the default alert threshold
is **0.8**.

## 2. Prerequisites (on-device software)

Raspberry Pi 5 (8 GB) with **Raspberry Pi OS Bookworm 64-bit** — the Hailo
stack is apt-packaged for Raspberry Pi OS (Ubuntu is not supported without a
Hailo Developer Zone account):

```bash
sudo apt update && sudo apt install -y hailo-all
sudo reboot
hailortcli fw-control identify        # verify the Hailo-8 responds
```

Add `dtparam=pciex1_gen=3` to `/boot/firmware/config.txt` for full PCIe
bandwidth.

Then install the Hailo apps suite (CLIP's current home — the standalone
`hailo-CLIP` repo requires the older TAPPAS 3.3x stack and will not work
with `hailo-all` 5.x):

```bash
git clone https://github.com/hailo-ai/hailo-apps
cd hailo-apps && sudo ./install.sh
```

**CLIP text-side files**: Hailo no longer distributes the tokenizer, token
embedding LUT, or text projection. Generate them from the OpenAI CLIP weights
(`openai/clip-vit-base-patch32` on HuggingFace) and place:
- `clip_tokenizer.json` (the repo's `tokenizer.json`) → `/usr/local/hailo/resources/json/`
- `token_embedding_lut.npy` (`text_model.embeddings.token_embedding.weight`, float32 49408×512) → `/usr/local/hailo/resources/npy/`
- `text_projection.npy` (projection in `x @ proj` orientation — HF weight transposed / TF kernel as-is, float32 512×512) → `/usr/local/hailo/resources/npy/`

Finally, the bridge dependencies into the hailo-apps venv:

```bash
~/hailo-apps/venv_hailo_apps/bin/pip install iotconnect-sdk-lite opencv-python psutil
```

## 3. Import the HCLIP Template

1. In /IOTCONNECT: **Devices → Templates → Create Template → Import** with
   [HCLIP-template.json](HCLIP-template.json) (attributes + the five commands).
2. Create a device from it and download `iotcDeviceConfig.json`,
   `device-cert.pem`, `device-pkey.pem` into this directory on the board
   (never commit these).

## 4. Run

```bash
./run.sh                     # defaults to /dev/video0
```

The hailo-apps CLIP GUI opens on the local display (prompt box, threshold
slider, probability bars), `[iotc] connected` confirms the cloud link, and the
booth web pages serve on port 8080.

## 5. Using the Demo

### Cloud commands (C2D)

| Command | Argument | Effect |
|---|---|---|
| `set-prompt` | text | Replace all prompts with this one |
| `add-prompt` | text | Append a prompt (stacks with existing) |
| `del-prompt` | — | Remove the most recently added prompt |
| `clear-prompts` | — | Remove all prompts |
| `set-threshold` | 0–1 | Alert threshold on `top_score` |

Telemetry @1 Hz: `top_prompt`, `top_score`, `scores` (JSON map),
`fps`, `npu_temp`, `cpu_temp`, `alert`.

Notes:

- **Six prompt slots maximum** (the matcher's fixed capacity); `add-prompt`
  fails with an ack message when full.
- **Scores are softmax probabilities**: they compete with each other and sum
  toward 1. With a single prompt loaded the score is always 1.0 — load at
  least two prompts (e.g. your target + `something else`) for meaningful
  numbers.
- `npu_temp` reports −1 (the current hailo_pci driver exposes no thermal
  sensor).

### Web pages (embed in dashboard widgets, port 8080)

| URL | Contents |
|---|---|
| `/` | Combined view: live stream + score bars + fps/temps + command ticker |
| `/top` | Hero view: top prompt in large type, giant score, animated match reveal |
| `/prompts` | Numbered list of loaded prompts |
| `/camera` | Full-bleed live stream |
| `/state.json` | Raw state (JSON) |

> [!TIP]
> The /IOTCONNECT dashboard is HTTPS; allow mixed content for the dashboard
> origin in the viewing browser (padlock → Site settings → Insecure content:
> Allow) and give the board a DHCP reservation so widget URLs stay stable.

### Suggested gauges

| Gauge | Range | Zones |
|---|---|---|
| `top_score` | 0–1 | 0–0.5 gray `#898781`, 0.5–0.8 amber `#fab219`, 0.8–1 green `#0ca30c` |
| `fps` | 0–35 | <15 red `#d03b3b`, 15–25 orange `#ec835a`, ≥25 green `#0ca30c` |
| `cpu_temp` | 0–100 | <65 green, 65–75 amber, >75 orange/red (throttles at 85) |

## Known quirks

- `hailo-clip`/the bridge **segfaults with `--input <video file>`** (upstream
  file-loop bug); camera input is solid.
- The app retitles its process to `Hailo Python App` — use that for
  `pgrep`/`pkill`.
- Use Ethernet for management; Pi 5 onboard WiFi proved unreliable under load
  on this build.
