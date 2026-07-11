# RZ/V2H EVK — /IOTCONNECT AI Demo Walkthrough

A guided tour of the full demo experience: what runs on the board, which AI models are behind each
button, how the /IOTCONNECT cloud interaction works, and a suggested script for presenting it.

---

## 1. The Experience at a Glance

Two USB cameras feed two independent inference engines on the Renesas RZ/V2H — the dedicated
**DRP-AI accelerator** and the **Cortex-A55 CPU cluster** — while every result, metric, and control
flows through **/IOTCONNECT** over MQTT. Everything is watchable live in a browser; no HDMI monitor
viewing is required.

```
  Camera 1 (C920) ──► DRP-AI accelerator ──► HDMI display ──► /drpai web feed
                       (EdgeYOLO / YOLOv3 /                    (desktop capture)
                        YOLOX+U-Net / FaceNet)
  Camera 2 (C920) ──► Cortex-A55 CPU     ──────────────────► /cv web feed
                       (OpenCV Haar detection)
                              │
                              ▼ telemetry every 10 s          ▲ commands (launch_drpai,
                        MQTT over TLS (AWS)                   │  start_detection, OTA ...)
                              └────────► /IOTCONNECT ◄────────┘
                                          dashboard
```

The punchline of the demo: **the same board runs a hardware-accelerated 188 MB YOLOv3 at full camera
rate on the DRP-AI while the CPUs stay almost idle** — and the cloud can switch between five
different AI workloads with a button press, with no models resident until asked for.

---

## 2. What Is Running on the Board

- **Board**: Renesas RZ/V2H EVK (4× Cortex-A55 + 2× Cortex-A76, DRP-AI accelerator, 16 GB RAM),
  booted from the eSD image of the Renesas RZ/V AI SDK v6.00 (Yocto Linux, Weston/Wayland desktop).
- **Cameras**: 2× Logitech C920 (Camera 1 = `/dev/video0`, reserved by DRP-AI demos;
  Camera 2 = `/dev/video2`, used by the CPU detection).
- **App**: `/opt/demo/app.py` — connects to /IOTCONNECT, streams telemetry, executes cloud
  commands, manages the DRP-AI demo binaries as subprocesses, and serves all video feeds as
  MJPEG at `http://<board-ip>:8080/`.
- Board-side quick-start commands: `cat ~/readme.txt` on the board.

---

## 3. The AI Models

All DRP-AI models are compiled ahead-of-time with the DRP-AI TVM toolchain into a `deploy.so`
object. **Nothing is resident until launched**: each dashboard button loads its model into DRP-AI
memory on demand (a few seconds), and launching a demo replaces the previous one — only one DRP-AI
workload runs at a time. Roughly **880 MB of model artifacts** are staged on the SD card in total.

| Command | Demo | Engine | Model(s) | Size on disk | Input | Use case |
|---|---|---|---|---|---|---|
| `launch_drpai coco` | Q08 Object Counter (COCO) | DRP-AI | EdgeYOLO-M, 80 COCO classes | 55 MB | 416×416 | Count people/objects in retail, safety, occupancy scenarios |
| `launch_drpai animal` | Q08 Object Counter (Animals) | DRP-AI | EdgeYOLO-M, animal classes | 55 MB | 416×416 | Wildlife/livestock monitoring |
| `launch_drpai vehicle` | Q08 Object Counter (Vehicles) | DRP-AI | EdgeYOLO-M, vehicle classes | 55 MB | 416×416 | Traffic/parking analytics |
| `launch_drpai r01` | R01 Object Detection | DRP-AI | YOLOv3 (full), 80 COCO classes | 188 MB | 416×416 | General-purpose detection with per-class confidence |
| `launch_drpai meter` | Q13 Analog Meter Reader | DRP-AI ×2 | YOLOX (gauge locator) + U-Net (needle segmentation) | 165 MB + 70 MB | camera frame → gauge crop | Industrial retrofit: digitize legacy analog gauges |
| `launch_drpai expiry` | Q06 Expiry Date OCR | DRP-AI + CPU | YOLOv3 (date-region detector) + Tesseract OCR | 187 MB | 416×416 | Food/pharma packaging date verification |
| `launch_drpai face_auth` | Q02 Face Authentication | DRP-AI | FaceNet (128-d face embeddings) | 94 MB | face crop | ID-vs-live-face verification, access control |
| `start_detection` | CPU face/person detection | Cortex-A55 | OpenCV Haar cascades (frontal-face + full-body) | < 2 MB | 640×480 | The CPU baseline that makes the DRP-AI contrast visible |

**Performance context** (as observed on this board):

- DRP-AI demos run at full camera rate; R01's on-screen post-processing overhead measures ~11–22 ms
  per frame. FaceNet's one-shot capture-plus-inference in Q02 measured ~460 ms.
- The CPU Haar path is deliberately throttled to ~5 fps and reports its per-frame inference time in
  telemetry (`inference_time_ms`) — typically an order of magnitude slower than the accelerator,
  while consuming CPU the DRP-AI demos don't.
- Model load time on launch is a few seconds (dominated by reading the `deploy.so` from SD).

---

## 4. Suggested Demo Script

1. **Boot and start.** Power the board (100 W USB-PD), wait for the Weston desktop, then SSH in and
   run the start block from `~/readme.txt`. The log prints the feeds URL and the /IOTCONNECT
   connection sequence — worth showing (Section 5).
2. **Open two browser tabs**: the /IOTCONNECT dashboard, and `http://<board-ip>:8080/` (all four
   video panels). Point out telemetry ticking every 10 s with CPU %, temperatures, and memory.
3. **`coco` (Q08 Counter)** — the crowd-pleaser. Point Camera 1 at the audience: live boxes and
   per-class counts on the HDMI feed. Note the board's CPU % barely moves — it's all DRP-AI.
4. **`r01` (YOLOv3)** — swap workloads live. One button unloads EdgeYOLO and loads the 188 MB
   YOLOv3; detections with confidence percentages appear a few seconds later. This is the
   "fleet-managed model swap" story.
5. **`start_detection` (CPU baseline)** — runs simultaneously on Camera 2. Compare the `/cv` panel
   (~5 fps, `inference_time_ms` in telemetry, CPU % up) against the DRP-AI panel (fluid). One board,
   two engines, both feeding one dashboard.
6. **`meter` (Q13)** — the industrial story: YOLOX finds the gauge, U-Net segments the needle, a
   classical angle calculation produces a value. Interactive: follow the on-screen calibration pages
   with the mouse (Start → confirm gauge → click min/max). Ships with `sample_image.jpg` /
   `video_sample.mp4` if no physical gauge is at hand.
7. **`face_auth` (Q02)** — audience participation: single-click **Add ID image**, then **Validate**.
   ⚠ **Single clicks only — a double-click anywhere is the app's quit gesture** (relaunch from the
   dashboard if it happens).
8. **`expiry` (Q06)** — hold up product packaging; YOLOv3 finds the date region, Tesseract reads it.
9. **Close with OTA**: mention that the running app itself was delivered and is updatable via the
   `file-download` command — /IOTCONNECT pushes a package URL, the app downloads, re-installs, and
   restarts itself.

---

## 5. The /IOTCONNECT Interaction

**Connection flow** (visible in the app log on every start):

1. **Discovery** — `https://discovery.iotconnect.io/...` resolves the tenant (CPID) and environment
   to the right regional endpoint.
2. **Identity** — the device (`uid`, e.g. `mclRZV2Hai1`) retrieves its MQTT broker details.
3. **MQTT connect** — mutual-TLS with the device's X.509 certificate (`device-cert.pem` /
   `device-pkey.pem`, provisioned during onboarding); connects in under a second on this network.

**Telemetry** — one JSON record every 10 s against the `rzv2hAI2` template, mixing system health,
CPU-inference results, and DRP-AI state (full field reference in [README.md](README.md#telemetry)):

```json
{"cpu_percent": 43.9, "memory_percent": 6.7, "cpu_temp_0_c": 53.0, "cpu_temp_1_c": 55.0,
 "drpai_present": true, "drpai_demo_active": true, "drpai_demo_name": "R01 Object Detection",
 "cv_active": false, "face_count": 0, "person_count": 0, "inference_time_ms": 0.0, ...}
```

**Commands (cloud → device)** — each dashboard button publishes a command to the device's MQTT
command topic; the app executes it and returns an **ack** (success/failure with a status message),
which the dashboard displays ("Executed Ack"):

| Command | Effect |
|---|---|
| `launch_drpai <demo>` | Stop current DRP-AI demo (if any), load the requested model, start it |
| `stop_drpai` | Terminate the DRP-AI demo, clear its display |
| `start_detection` / `stop_detection` | Start/stop CPU Haar detection (picks a free camera) |
| `set_confidence <0.0–1.0>` | Adjust CPU detection sensitivity |
| `file-download <url>` | OTA: download a package, re-install, restart the app |

**Why this architecture is the story**: the device is a *managed AI endpoint*. Model selection,
demo orchestration, sensitivity tuning, and software updates all happen from the cloud — while the
video itself stays local (LAN MJPEG streams), keeping bandwidth and privacy under control.

---

## 6. Behavior Notes & Quirks

- **Camera arbitration**: a camera has exactly one consumer. Raw feeds (`/cam1`, `/cam2`) yield
  automatically with an "in use" card whenever a DRP-AI demo or the CPU detection owns the device,
  and resume when it's released. DRP-AI binaries hardcode Camera 1 (`/dev/video0`).
- **Desktop capture is ~2 fps** — that's the Weston screenshot ceiling, not a fault. Fine for
  demoing; the HDMI output itself is fluid.
- **`meter` / `expiry` / `face_auth` are mouse-driven** — they need the physical mouse on the HDMI
  desktop. The web panel shows what's happening but can't click.
- **Face auth exits on double-click** — by design (its quit gesture). Single clicks only.
- **`drpai_*` telemetry fields stay 0 with stock binaries** — the Renesas demos render results to
  the display only. Exporting counts/timing to telemetry requires rebuilding them with the patches
  in [`patches/`](patches/) (see [README.md §7](README.md#7-drp-ai-inference-telemetry-optional)).
- **Power matters**: use the recommended 100 W USB-PD supply. Brownouts during boot corrupt the SD
  card (observed first-hand — that's how this board got reflashed).
- **HDMI must be occupied** (monitor or dummy plug) for Weston, and therefore for any DRP-AI demo,
  to start.
