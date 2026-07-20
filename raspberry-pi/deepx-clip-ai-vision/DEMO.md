# Ask the Camera

### Cloud-Reprogrammable AI Vision — DEEPX DX-M1 + Raspberry Pi 5 + Avnet /IOTCONNECT

**Type a sentence into a cloud dashboard, and an edge camera starts looking for
it — in about one second, with no retraining, no new model, no redeploy.**

---

## What this demo is

Every conventional edge-AI camera ships knowing a fixed list of things it can
detect. This demo is different: its job description changes from the cloud in
real time.

The camera runs **CLIP**, a vision-language model, on the **DEEPX DX-M1** — a
25-TOPS M.2 accelerator drawing 3–5 W. CLIP maps images and sentences into the
same mathematical space, so "what is the camera seeing?" becomes "how close is
this frame to this sentence?" A viewer types any plain-English prompt into the
/IOTCONNECT dashboard:

> *a person waving* · *someone wearing safety glasses* · *a red toolbox* · *an empty room with nobody present*

Within a second or two, the DX-M1 is scoring every camera frame against that
sentence. When the described thing appears in front of the lens, the similarity
score spikes, an alert fires, and the dashboard lights up.

The audience decides what the camera looks for — live.

<img src="media/dashboard-screenshot.png" width="1200" alt="/IOTCONNECT dashboard: gauges for score, fps, and temperatures; one-touch prompt command buttons; embedded live pages showing the top prompt with its match reveal and the loaded prompt list">

*The /IOTCONNECT dashboard: telemetry gauges, one-touch prompt buttons, the
device command log, and the Pi's own live pages embedded right alongside —
shown here mid-match on "a person waving at the camera".*

## Why /IOTCONNECT is the difference-maker

The NPU makes the demo *possible*; /IOTCONNECT makes it a *product story*:

- **Commands down** — the prompt box on the dashboard is a C2D command
  (`set-prompt`). The same mechanism that re-tasks this camera scales to
  re-tasking ten thousand cameras: change what an entire fleet watches for with
  one command, no firmware rollout.
- **Telemetry up** — similarity scores, alert state, pipeline FPS, and silicon
  temperatures stream once per second into dashboards, rules, and alerts.
  The same data that drives the demo gauges drives real operations: thermal
  monitoring, health checks, SLA evidence.
- **One pane of glass** — gauges, score timelines, command buttons, and the
  device's own locally-served live view sit together in a single dashboard.
  An operator sees *and* steers the edge from one screen.
- **Zero-friction onboarding** — the device authenticates with per-device X.509
  certificates issued by /IOTCONNECT; drop three files on the board and it's a
  managed, secure fleet member.

The loop this demo closes — describe intent in natural language, push it to the
edge, watch structured results stream back — is the shape of modern industrial
monitoring: safety-gear compliance, zone occupancy, spill and smoke detection,
process verification. All of those are just prompts.

## Architecture

```
  /IOTCONNECT dashboard  ── set-prompt "a person waving" ──►  Raspberry Pi 5
      ▲                                                        │  bridge app
      │ telemetry: top_score, scores, fps,                     ▼
      │ npu_temp, cpu_temp, alert (1 Hz, MQTT/TLS)      CLIP text encoder (CPU)
      └────────────────────────────────────────┐               │ prompt embedding
                                               │               ▼
  Booth web pages (served from the Pi):   CLIP image encoder .dxnn ── DX-M1 NPU
  /camera  /top  /prompts  (embed as           ▲     (~200 FPS capability)
  dashboard widgets)                           │
                                          USB camera
```

The image encoder runs on the NPU every frame; the text encoder only runs when
a prompt changes — which is why cloud re-tasking is nearly instant.

---

## Bringing up the demo (software already on the board)

**What you need:** the demo Raspberry Pi 5 (DX-M1 fitted), its USB camera, an
HDMI display, the 27 W USB-C power supply, and Wi-Fi the board already knows
(or Ethernet).

1. **Connect and power on.** Camera in any USB-A port, HDMI to the display,
   then power. The board boots to the desktop in under a minute.

2. **Start the demo.** Open a terminal on the desktop (or SSH in) and run:

   ```bash
   ~/deepx/dx_clip_demo/bridge/run.sh
   ```

   Within ~30 seconds you'll see: the annotated camera window on the display,
   `[iotc] connected` in the terminal (cloud link up), and
   `[web] serving booth page on port 8080`.

3. **Open the dashboard.** Log into
   [console.iotconnect.io](https://console.iotconnect.io), open the demo
   device's dashboard. The gauges are live as soon as the demo starts.

4. **Drive it from the cloud.** Use the dashboard's command buttons (or Device
   Commands) to send `set-prompt` with any description — then act it out in
   front of the camera and watch `top_score` spike, the alert fire, and the
   hero page flash its match reveal.

5. **Local fallback controls.** In the demo terminal: type any sentence to add
   it as a prompt, `list` to see all prompts and scores, `del` to remove the
   last one, `quit` (or `q` in the video window) to exit.

That's the entire bring-up: power, one command, dashboard.

### If something doesn't look right

| Symptom | Fix |
|---|---|
| No camera window | Check the USB camera is seated; rerun `run.sh` |
| Frozen video / identical scores | Camera hiccup — quit (`q`) and rerun `run.sh` |
| No `[iotc] connected` | Board has no internet, or the three credential files are missing from `bridge/` |
| Dashboard widgets blank | Booth browser must allow mixed content for the dashboard origin; confirm the Pi's IP in the widget URLs |
| NPU not found errors | `lspci` should list `DEEPX DX_M1`; reseat the M.2 module / check `dxrt-cli --status` |

---

## Appendix: full installation

To build this demo from a blank SD card: install Ubuntu Server 24.04 (64-bit)
on a Pi 5 (8 GB), enable PCIe Gen 3 (`dtparam=pciex1`, `dtparam=pciex1_gen=3`),
install the DEEPX stack from
[dx-all-suite](https://github.com/DEEPX-AI/dx-all-suite)
(`dx-runtime/install.sh --all`), flash the bundled DX-M1 firmware
(`dxrt-cli -u`), set up
[dx_clip_demo](https://github.com/DEEPX-AI/dx_clip_demo)
(`./setup.sh --app_type=opencv`, then pin `opencv-python<5` in the venv), apply
the fixes patch (`patches/dx_clip_demo-fixes.patch` — camera resilience, live-camera
latency, and score responsiveness), install `iotconnect-sdk-lite` + `psutil` into the
demo venv, and copy this `bridge/` directory into the `dx_clip_demo` repo root.
Full command-by-command steps live in [README.md](README.md) and the
patch notes in this repository.
