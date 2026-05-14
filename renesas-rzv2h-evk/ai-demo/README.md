# RZ/V2H EVK — AI Inference Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the Renesas RZ/V2H EVK to a full AI inference demo — Python computer-vision
face
and person detection on a USB camera, plus cloud-launched DRP-AI hardware-accelerated demos rendered on the HDMI
display.

> [!IMPORTANT]
> Complete
> the [/IOTCONNECT quickstart guide for the RZ/V2H EVK](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/renesas-rzv2h-evk/README.md)
> before proceeding.

## 1. Introduction

Python OpenCV Haar cascade inference runs on the USB camera for face and full-body person detection on the A55 CPU
cores. Separately, any of the Renesas DRP-AI hardware demos can be launched via a C2D command — the `object_counter` binary
runs YOLOv3 on the DRP-AI accelerator and renders bounding boxes and object counts on the HDMI display. Both can run
simultaneously since they use independent hardware.

## 2. Prerequisites

**Additional hardware required:**

- USB camera supporting YUYV 640×480 @ 30fps (e.g. Logitech BRIO, C920)
- HDMI monitor connected with Weston running (required to launch DRP-AI demos)

**AI SDK binaries on the board.** The `object_counter` binary and model weights must be present at `/home/weston/tvm_q08/`. 
Deploy them from your host PC using a sparse clone of the Renesas AI SDK GitHub repo:

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/renesas-rz/rzv_ai_sdk.git ~/ai_sdk_work/ai_sdk_setup/rzv_ai_sdk
cd ~/ai_sdk_work/ai_sdk_setup/rzv_ai_sdk
git sparse-checkout set Q08_object_counter/exe_v2h
ssh root@<board-ip> "mkdir -p /home/weston/tvm_q08"
scp -r Q08_object_counter/exe_v2h/* root@<board-ip>:/home/weston/tvm_q08/
```

To verify on the board:

```bash
ls /home/weston/tvm_q08/object_counter
```

## 3. Change Device Template

Before installing, change your device's template to `rzv2hAI2` in the /IOTCONNECT online platform:

1. Open your /IOTCONNECT instance and navigate to your device's page.
2. Locate the **Template** field and click the edit icon.
3. Select the `rzv2hAI2` template from the drop-down and save.

> [!TIP]
> If the `rzv2hAI2` template is not yet present in your /IOTCONNECT instance, import it
> from [rzv2h-ai-template.json](rzv2h-ai-template.json)
> via **Templates → Create Template → Import**.

## 4. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/renesas-rzv2h-evk/ai-demo/package.tar.gz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

### Run

```bash
python3 app.py
```

## 5. Using the Demo

The app connects to /IOTCONNECT and begins sending telemetry immediately. CV inference and DRP-AI demos are started via
cloud commands.

### Telemetry

**System Performance**

| Attribute        | Type    | Description                                   |
|------------------|---------|-----------------------------------------------|
| `cpu_percent`    | DECIMAL | CPU utilisation (%)                           |
| `memory_percent` | DECIMAL | RAM usage (%)                                 |
| `memory_used_mb` | DECIMAL | Used RAM (MB)                                 |
| `cpu_temp_0_c`   | DECIMAL | Cortex-A55 cluster temperature (°C)           |
| `cpu_temp_1_c`   | DECIMAL | Cortex-A76 cluster temperature (°C)           |
| `drpai_present`  | BOOLEAN | DRP-AI device node accessible (`/dev/drpai0`) |
| `sdk_version`    | STRING  | IoTConnect SDK version                        |
| `random`         | INTEGER | Connectivity heartbeat                        |

**AI Inference**

| Attribute           | Type    | Description                          |
|---------------------|---------|--------------------------------------|
| `cv_active`         | BOOLEAN | Python OpenCV inference running      |
| `face_count`        | INTEGER | Faces detected in current frame      |
| `person_count`      | INTEGER | Full-body persons detected           |
| `total_detections`  | INTEGER | Faces + persons per frame            |
| `inference_time_ms` | DECIMAL | Python inference time per frame (ms) |
| `drpai_demo_active` | BOOLEAN | DRP-AI hardware demo running on HDMI |
| `drpai_demo_name`   | STRING  | Active DRP-AI demo name              |

### Commands

| Command           | Parameter                                   | Description                                      |
|-------------------|---------------------------------------------|--------------------------------------------------|
| `start_detection` | —                                           | Start Python face/person detection on USB camera |
| `stop_detection`  | —                                           | Stop Python detection                            |
| `launch_drpai`    | see [Full Demo Matrix](#6-full-demo-matrix) | Launch any DRP-AI demo on HDMI display           |
| `stop_drpai`      | —                                           | Stop DRP-AI demo                                 |
| `set_confidence`  | `0.0`–`1.0`                                 | Adjust detection sensitivity                     |
| `file-download`   | URL                                         | Download and apply OTA update package            |

### Example Workflow

1. Send **`start_detection`** → face/person counts appear in telemetry
2. Send **`launch_drpai`** with parameter `coco` → object detection starts on HDMI
3. Watch `drpai_demo_active` go `true` and `drpai_demo_name` appear in Live Data
4. Send **`stop_drpai`** → demo stops, display cleared
5. Send **`stop_detection`** → CV inference halts, counts return to zero

## 6. Full Demo Matrix

Every demo from the Renesas RZ/V2H AI SDK is supported. The `launch_drpai` command parameter maps to the table below.
Per-frame results flow through `/tmp/drpai_<demo>_results.json` (atomic rename writes). Demos marked "ui_only" require
mouse interaction on the HDMI display and do not emit structured inference JSON — they still report `drpai_demo_active`
and `drpai_demo_name`.

| Parameter                     | Demo                             | Kind         | Telemetry output fields                                                         |
|-------------------------------|----------------------------------|--------------|---------------------------------------------------------------------------------|
| `coco` / `animal` / `vehicle` | Q08 Object Counter               | detector     | `drpai_total`, `drpai_person_count`, `drpai_counts`                             |
| `meter`                       | Q13 Analog Meter Reader          | meter        | `meter_value`, `meter_min/max`, `meter_page`, `meter_yolox_ms`, `meter_unet_ms` |
| `footfall`                    | Q01 Footfall Counter             | detector     | `drpai_total`                                                                   |
| `face_auth`                   | Q02 Face Authentication          | ui_only      | process state only                                                              |
| `parking`                     | Q03 Smart Parking                | ui_only      | process state only                                                              |
| `fish_class`                  | Q04 Fish Classification          | classifier   | `drpai_primary_class`, `drpai_primary_confidence`                               |
| `activity`                    | Q05 Suspicious Activity          | activity     | `drpai_primary_class` (violence/non_violence), `drpai_primary_confidence`       |
| `expiry`                      | Q06 Expiry Date Detection        | ui_only      | process state only                                                              |
| `plant`                       | Q07 Plant Disease Classification | classifier   | `drpai_primary_class`, `drpai_primary_confidence`                               |
| `crack`                       | Q09 Crack Segmentation           | segmentation | timing only (`drpai_inference_time_ms`)                                         |
| `suspicious`                  | Q10 Suspicious Person Detection  | detector     | `drpai_total`                                                                   |
| `fish_det`                    | Q11 Fish Detection               | detector     | `drpai_total`                                                                   |
| `yoga`                        | Q12 Yoga Pose Estimation         | pose         | `drpai_primary_class` (pose name), `drpai_primary_confidence`                   |
| `r01`                         | R01 Generic Object Detection     | detector     | `drpai_total`, `drpai_primary_class`, `drpai_primary_confidence`                |

All demos also report `drpai_inference_time_ms`, `drpai_pre_time_ms`, `drpai_post_time_ms`, and `drpai_demo_kind`.

### Q13 Analog Meter Reader

Q13 pipelines two DRP-AI models: YOLOX locates the gauge in the frame, then U-Net segments the needle. A classical
angle-calculation step converts the needle position to a scalar reading. The demo is stateful:

1. **Page 1** — position camera, click Start
2. **Page 2** — YOLOX locates the meter; user confirms
3. **Page 3** — user clicks min/max values on the gauge to calibrate
4. **Page 5** — live reading; `meter_value` streams to /IOTCONNECT

The `meter_page` attribute tracks the current step. `meter_calibration_warning` goes `true` when Q13 detects high
deviation between the current reading and the learned center.

## 7. DRP-AI Inference Telemetry (Optional)

The stock `object_counter` binary only renders results to the HDMI display and exports nothing. To surface DRP-AI
detection counts and timing in telemetry, rebuild the binary with the patch in [
`patches/object_counter-iotconnect.patch`](patches/object_counter-iotconnect.patch).

The patch adds writes to `/tmp/drpai_results.json` (tmpfs, atomic rename) each frame. The app reads this file every
telemetry tick and forwards the values under the `drpai_*` attributes.

Use `build-and-deploy.sh` from the `patches/` directory:

```bash
cd renesas-rzv2h-evk/ai-demo/patches
./build-and-deploy.sh 192.168.68.66 q08              # build + deploy Q08
./build-and-deploy.sh 192.168.68.66 q13 q12 r01      # multiple demos
./build-and-deploy.sh 192.168.68.66 all               # every demo
```

Without the patches, the `drpai_*` / `meter_*` telemetry fields stay at zero when a DRP-AI demo is running — only
CPU/memory/temperature/Python-CV fields populate.

## 8. Troubleshooting

| Problem                               | Resolution                                                                        |
|---------------------------------------|-----------------------------------------------------------------------------------|
| `launch_drpai` returns "Failed"       | Verify `/home/weston/tvm_q08/object_counter` exists and HDMI monitor is connected |
| DRP-AI demo exits immediately         | Ensure Wayland/Weston is running (`ps aux                                         | grep weston`) |
| No camera frames in CV                | Check `v4l2-ctl --list-devices`; USB camera must be on `/dev/video0`              |
| `ModuleNotFoundError: system_monitor` | Ensure `system_monitor.py` is in the same directory as `app.py`                   |
