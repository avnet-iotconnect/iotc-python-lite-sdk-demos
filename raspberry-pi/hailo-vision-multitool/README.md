# Hailo Vision Multi-Tool — Cloud-Retaskable CNN Vision

One Raspberry Pi 5 + Hailo-8, three heavyweight YOLOv8m pipelines — **object
detection, pose estimation, instance segmentation** — switched live from the
/IOTCONNECT dashboard. Where the [CLIP demo](../hailo-clip-ai-vision) re-aims
*what* the camera looks for, this demo re-tasks *the entire neural workload*:
`set-mode pose` tears down the running pipeline and boots the next one in
seconds, at full camera rate. This is the workload class the Hailo-8's
dataflow architecture excels at (measured ~30 fps in all three modes).

## Prerequisites

Same base as the CLIP demo (Raspberry Pi OS Bookworm, `hailo-all`,
`hailo-apps` installed — see its
[README](../hailo-clip-ai-vision/README.md#2-prerequisites-on-device-software)
sections 2, skipping the CLIP text-side files), plus:

```bash
~/hailo-apps/venv_hailo_apps/bin/pip install iotconnect-sdk-lite opencv-python
```

The yolov8m / yolov8m_pose / yolov8m_seg HEFs are installed by the hailo-apps
installer.

## /IOTCONNECT Setup

1. Import [HVISION-template.json](HVISION-template.json) (**Devices →
   Templates → Create Template → Import**).
2. Create a device from it; download `iotcDeviceConfig.json`,
   `device-cert.pem`, `device-pkey.pem` into the `src/` directory on the
   board (never commit these). Without them the demo runs fully offline —
   the web page's mode buttons still work.

## Run

```bash
./src/run.sh                      # defaults: /dev/video0, detect mode, port 8081
```

## Using the Demo

| Command | Argument | Effect |
|---|---|---|
| `set-mode` | `detect` \| `pose` \| `segment` | Swap the active pipeline live (~10–20 s) |
| `set-alert-count` | integer | Alert fires when `person_count` ≥ this (default 3) |

Telemetry @1 Hz: `mode`, `person_count`, `object_count`, `objects`
(JSON label→count), `top_object`, `fps`, `cpu_temp`, `alert`.

**Web pages** (embed in dashboard widgets, port 8081):

| URL | Contents |
|---|---|
| `/` | Control page: live annotated stream, people counter, object counts, **mode buttons** (local fallback control, no cloud needed) |
| `/objects` | **Animated object board** — every detected object type becomes an emoji tile that springs in, bobs while in view, bumps its count badge on change, and shrinks away when it leaves; page flips to a flashing red CROWD ALERT when `person_count` crosses the threshold |
| `/camera` | Full-bleed annotated stream |
| `/state.json` | Raw state (JSON) |
| `/cmd?name=set-mode&arg=pose` | HTTP control endpoint |

### Booth flow

1. Start in `detect` — hold up a phone/cup/bottle, watch labeled counts
   stream to the dashboard.
2. `set-mode pose` from the dashboard — skeletons appear; invite the
   audience to strike a pose.
3. `set-mode segment` — pixel-perfect masks.
4. Crowd gathers → `person_count` crosses the alert threshold → dashboard
   alert fires: "3+ people at the booth."

Run one Hailo demo at a time (one camera, one NPU): `run.sh` stops the CLIP
demo automatically; start the CLIP demo's `run.sh` to hand back.

## Suggested gauges

`person_count` 0–10 (alert marker at your threshold), `fps` 0–35 (green
≥25), `cpu_temp` 0–100 (green <65, amber 65–75, red >75). `mode` and
`top_object` as text tiles; `objects` in a table widget.
