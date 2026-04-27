# RZ/V2H EVK — AI Inference Demo

This demo connects the Renesas RZ/V2H EVK to /IOTCONNECT with full AI inference
integration: real-time face and person detection runs on the USB camera via Python
OpenCV, while the Renesas DRP-AI hardware accelerator demos (YOLO-based object
detection) can be launched and controlled from the cloud via C2D commands and display
their results on the connected HDMI monitor.

## Architecture

```
                    /IOTCONNECT
                         │
              C2D commands│ Telemetry
                         │
                    [app.py]
                   /        \
     [system_monitor.py]  [OpenCV Haar Cascade]
       CPU / Memory           USB Camera
       Temperature            Face + Person Detection
       DRP-AI status          Inference timing
                         \
                    [DRP-AI C++ Binary] ─── HDMI Display
                    (object_counter)
                    COCO / Animal / Vehicle
```

### Python CV Inference (no additional downloads needed)
Uses OpenCV's built-in Haar cascade classifiers — **haarcascade_frontalface_default.xml**
(faces) and **haarcascade_fullbody.xml** (full-body persons). These ship with every
OpenCV installation and run on the A55 CPU cores at ~5 fps, leaving the DRP-AI
hardware free for the C++ demo.

### DRP-AI Hardware Demos
The Renesas AI SDK `object_counter` binary is launched as a managed subprocess via
C2D command. It uses the DRP-AI accelerator to run YOLOv3 inference at full speed
and renders bounding boxes and object counts on the HDMI display. Three modes are
available: COCO (80 classes), Animal, and Vehicle.

### DRP-AI Inference Telemetry (requires patched binary)
The stock `object_counter` binary only renders results to the HDMI display — it
has no way to export them. To surface real DRP-AI detection counts and timing in
IoTConnect telemetry, rebuild `object_counter` with the patch in
[`patches/object_counter-iotconnect.patch`](patches/object_counter-iotconnect.patch).

The patch adds ~25 lines that write per-frame results to
`/tmp/drpai_results.json` (tmpfs, atomic rename). Python reads this file every
telemetry tick and forwards the values under the `drpai_*` attributes.

Build and deploy any patched demo — the script auto-applies the patch if
needed, auto-downloads missing model weights from Renesas' GitHub releases,
and scp's the built binary and weights to the right folder on the board.

```bash
cd renesas-rzv2h-evk/ai-demo/patches
./build-and-deploy.sh 192.168.68.66 q08              # build + deploy Q08
./build-and-deploy.sh 192.168.68.66 q13 q12 r01      # multiple at once
./build-and-deploy.sh 192.168.68.66 all              # every demo
```

Without the patches, the `drpai_*` / `meter_*` telemetry fields stay at zero
when the DRP-AI demo is running — only CPU / memory / temperature / Python-CV
fields populate.

### Full Demo Matrix

Every demo from the Renesas RZ/V2H AI SDK is wired in. The `launch_drpai` command
parameter maps to the table below. Per-frame results flow through
`/tmp/drpai_<demo>_results.json` (atomic rename writes). Demos marked "UI-only"
don't emit structured inference JSON (mouse-driven calibration / enrollment);
they still report `drpai_demo_active` and `drpai_demo_name` so you know when
they're running.

| Param | Demo | Kind | Output fields in telemetry |
|-------|------|------|-------|
| `coco` / `animal` / `vehicle` | Q08 Object Counter | detector | `drpai_total`, `drpai_person_count`, `drpai_counts` |
| `meter` | Q13 Analog Meter Reader | meter | `meter_value`, `meter_min/max`, `meter_page`, `meter_yolox_ms`, `meter_unet_ms` |
| `footfall` | Q01 Footfall Counter | detector | `drpai_total` |
| `face_auth` | Q02 Face Authentication | ui_only | process state only |
| `parking` | Q03 Smart Parking | ui_only | process state only |
| `fish_class` | Q04 Fish Classification | classifier | `drpai_primary_class`, `drpai_primary_confidence` |
| `activity` | Q05 Suspicious Activity | activity | `drpai_primary_class` (violence/non_violence), `drpai_primary_confidence` |
| `expiry` | Q06 Expiry Date Detection | ui_only | process state only |
| `plant` | Q07 Plant Disease Classification | classifier | `drpai_primary_class`, `drpai_primary_confidence` |
| `crack` | Q09 Crack Segmentation | segmentation | timing only (`drpai_inference_time_ms`) |
| `suspicious` | Q10 Suspicious Person Detection | detector | `drpai_total` |
| `fish_det` | Q11 Fish Detection | detector | `drpai_total` |
| `yoga` | Q12 Yoga Pose Estimation | pose | `drpai_primary_class` (pose name), `drpai_primary_confidence` |
| `r01` | R01 Generic Object Detection | detector | `drpai_total`, `drpai_primary_class`, `drpai_primary_confidence` |

All demos report the shared timing fields: `drpai_inference_time_ms`,
`drpai_pre_time_ms`, `drpai_post_time_ms`, plus `drpai_demo_kind` so dashboards
can style widgets conditionally on the active demo type.

### Q13 Analog Meter Reader (dual-model)
Q13 uses two models pipelined on the DRP-AI: YOLOX locates the gauge in the
frame, then U-Net segments the needle. A classical angle-calculation step
converts the needle position into a scalar reading. The demo is stateful:

1. **Page 1** — position camera, click Start
2. **Page 2** — YOLOX locates the meter; user confirms
3. **Page 3** — user clicks min/max values on the gauge to calibrate
4. **Page 5** — live reading; `meter_value` streams to IoTConnect

The telemetry `meter_page` attribute tracks which step the demo is on so your
dashboard can show a status badge (e.g. "waiting for calibration"). The
`meter_calibration_warning` boolean goes `true` when Q13 detects high deviation
between the current reading and the learned center — useful for triggering
recalibration alerts.

## Prerequisites

Complete the [board setup and onboarding steps](../README.md) first.

The following must already be set up on the board (from the AI SDK guide):

```
/home/weston/tvm_q08/
├── object_counter       ← DRP-AI demo binary
├── coco/                ← COCO model and labels
├── animal/              ← Animal model and labels
└── vehicle/             ← Vehicle model and labels
```

To verify:

```bash
ls /home/weston/tvm_q08/object_counter
```

## Setup

### 1. Import the device template

In /IOTCONNECT, import `rzv2h-ai-template.json` as the device template.

### 2. Place credential files

Copy your device credentials to `/opt/demo` on the board:

```bash
mkdir -p /opt/demo && cd /opt/demo
# Copy iotcDeviceConfig.json, device-cert.pem, device-pkey.pem here
```

### 3. Deploy the demo files

**Option A — Copy source files directly (SSH)**

```bash
scp renesas-rzv2h-evk/ai-demo/src/* root@<board-ip>:/opt/demo/
ssh root@<board-ip> "cd /opt/demo && bash install.sh && rm install.sh"
```

**Option B — OTA package**

Build the package on your host:

```bash
cd renesas-rzv2h-evk/ai-demo
bash create-package.sh
```

Host `package.tar.gz` on a web server, then send a `file-download` command from
/IOTCONNECT with the URL as the parameter.

## Run

```bash
cd /opt/demo
python3 app.py
```

The app connects to /IOTCONNECT and begins sending telemetry immediately. CV inference
and DRP-AI demos are started via cloud commands.

## Telemetry

### System Performance

| Attribute | Type | Description |
|-----------|------|-------------|
| `cpu_percent` | DECIMAL | CPU utilisation (%) |
| `memory_percent` | DECIMAL | RAM usage (%) |
| `memory_used_mb` | DECIMAL | Used RAM (MB) |
| `cpu_temp_0_c` | DECIMAL | Cortex-A55 cluster temperature (°C) |
| `cpu_temp_1_c` | DECIMAL | Cortex-A76 cluster temperature (°C) |
| `drpai_present` | BOOLEAN | DRP-AI device node accessible (`/dev/drpai0`) |
| `sdk_version` | STRING | IoTConnect SDK version |
| `random` | INTEGER | Connectivity heartbeat |

### AI Inference

| Attribute | Type | Description |
|-----------|------|-------------|
| `cv_active` | BOOLEAN | Python OpenCV inference running |
| `face_count` | INTEGER | Faces detected in current frame |
| `person_count` | INTEGER | Full-body persons detected |
| `total_detections` | INTEGER | faces + persons per frame |
| `inference_time_ms` | DECIMAL | Python inference time per frame (ms) |
| `drpai_demo_active` | BOOLEAN | DRP-AI hardware demo running on HDMI |
| `drpai_demo_name` | STRING | Active DRP-AI demo name |

## C2D Commands

| Command | Parameter | Description |
|---------|-----------|-------------|
| `start_detection` | — | Start Python face/person detection on USB camera |
| `stop_detection` | — | Stop Python detection |
| `launch_drpai` | see demo matrix below | Launch any of 14 DRP-AI demos on HDMI display |
| `stop_drpai` | — | Stop DRP-AI demo |
| `set_confidence` | `0.0`–`1.0` | Adjust detection sensitivity |
| `file-download` | URL | Download and apply OTA update package |

### Example workflow

1. Send **`start_detection`** → face/person counts appear in telemetry
2. Send **`launch_drpai`** with parameter `coco` → object detection starts on HDMI
3. Watch `drpai_demo_active` go `true` and `drpai_demo_name` appear in Live Data
4. Send **`stop_drpai`** → demo stops, display cleared
5. Send **`stop_detection`** → CV inference halts, counts return to zero

## Notes

- The DRP-AI C++ demo and Python CV inference can run simultaneously. The DRP-AI
  binary uses its dedicated hardware accelerator; Python CV uses the A55 CPU cores.
- Haar cascade inference typically runs at 20–100ms per frame depending on frame
  content, leaving plenty of CPU for other tasks.
- The DRP-AI demo **requires a Wayland display** (HDMI monitor connected and weston
  running). The app auto-detects the active Wayland socket.
- Both the CV inference and DRP-AI demo are automatically stopped when an OTA
  update is applied so the application can restart cleanly.

## Troubleshooting

| Problem | Resolution |
|---------|------------|
| `launch_drpai` returns "Failed" | Verify `/home/weston/tvm_q08/object_counter` exists and HDMI monitor is connected |
| DRP-AI demo exits immediately | Ensure Wayland/Weston is running (`ps aux | grep weston`) |
| No camera frames in CV | Check `v4l2-ctl --list-devices`; USB camera must be on `/dev/video0` |
| `ModuleNotFoundError: system_monitor` | Ensure `system_monitor.py` is in the same directory as `app.py` |
