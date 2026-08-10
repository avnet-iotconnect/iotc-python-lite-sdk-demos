# Hailo Vision Multi-Tool — Cloud-Retaskable CNN Vision

One Raspberry Pi 5 + Hailo-8, three heavyweight YOLOv8m pipelines — **object
detection, pose estimation, instance segmentation** — switched live from the
/IOTCONNECT dashboard. `set-mode pose` tears down the running pipeline and
boots the next one in seconds, at full camera rate (measured ~30 fps in all
three modes). People and object counts stream to the cloud once per second,
and the board serves its own embeddable live pages, including an animated
object board.

## 1. Requirements

### Hardware
- Raspberry Pi 5 (8 GB recommended) with active cooler
- Hailo-8 M.2 AI accelerator module on an M.2 HAT
- USB UVC camera
- Ethernet recommended for management

### Software
Raspberry Pi OS Bookworm 64-bit. Install the Hailo stack and apps suite:

```bash
sudo apt update && sudo apt install -y hailo-all
echo -e "\n[all]\ndtparam=pciex1_gen=3" | sudo tee -a /boot/firmware/config.txt
sudo reboot
hailortcli fw-control identify          # verify the Hailo-8 responds

git clone https://github.com/hailo-ai/hailo-apps
cd hailo-apps && sudo ./install.sh      # installs models incl. yolov8m/pose/seg
```

Then the bridge dependencies into the hailo-apps virtual environment:

```bash
~/hailo-apps/venv_hailo_apps/bin/pip install iotconnect-sdk-lite opencv-python
```

## 2. /IOTCONNECT Setup

1. Import [HVISION-template.json](HVISION-template.json) (**Devices →
   Templates → Create Template → Import**).
2. Create a device from it; download `iotcDeviceConfig.json`,
   `device-cert.pem`, `device-pkey.pem` into the `src/` directory on the
   board (never commit these). Without them the demo runs fully offline —
   the web page's mode buttons still work.

## 3. Run

```bash
./src/run.sh                      # defaults: /dev/video0, detect mode, port 8081
```

## 4. Using the Demo

| Command | Argument | Effect |
|---|---|---|
| `set-mode` | `detect` \| `pose` \| `segment` | Swap the active pipeline live (~10–20 s) |
| `set-alert-count` | integer | Alert fires when `person_count` ≥ this (default 3) |

Telemetry @1 Hz: `mode`, `person_count`, `object_count`, `objects`
(JSON label→count), `top_object`, `fps`, `cpu_temp`, `alert`.

### Web pages (embed in dashboard widgets, port 8081)

| URL | Contents |
|---|---|
| `/` | Control page: live annotated stream, people counter, object counts, **mode buttons** (local fallback control, no cloud needed) |
| `/objects` | **Animated object board** — every detected object type becomes an emoji tile that springs in, bobs while in view, bumps its count badge on change, and shrinks away when it leaves; page flips to a flashing red CROWD ALERT when `person_count` crosses the threshold |
| `/camera` | Full-bleed annotated stream |
| `/state.json` | Raw state (JSON) |
| `/cmd?name=set-mode&arg=pose` | HTTP control endpoint |

> [!TIP]
> The /IOTCONNECT dashboard is HTTPS; allow mixed content for the dashboard
> origin in the viewing browser (padlock → Site settings → Insecure content:
> Allow) and give the board a DHCP reservation so widget URLs stay stable.

### Booth flow

1. Start in `detect` — hold up a phone/cup/bottle, watch labeled counts
   stream to the dashboard and tiles spring onto the object board.
2. `set-mode pose` from the dashboard — skeletons appear; invite the
   audience to strike a pose.
3. `set-mode segment` — pixel-perfect masks.
4. Crowd gathers → `person_count` crosses the alert threshold → dashboard
   alert fires and the object board flips to CROWD ALERT.

If another camera application is using the device, stop it first — one
pipeline owns the camera and NPU at a time.

## 5. Optional: Unified Demo Device (`set-demo`)

If the CLIP demo from this repository is also installed on the board, both
demos can share **one** /IOTCONNECT device and hand the camera/NPU to each
other from the cloud:

1. Import [HAILODEMO-template.json](HAILODEMO-template.json) — it carries the
   superset of both demos' telemetry and commands plus `set-demo`.
2. Create (or re-template) a device on it and place its
   `iotcDeviceConfig.json`, `device-cert.pem`, `device-pkey.pem` in
   `~/hailo-identity/` on the board. Both bridges prefer that folder over
   their local credentials when it exists.
3. Send `set-demo clip` or `set-demo vision` (from the dashboard or either
   demo's `/cmd` endpoint). The running demo acks, exits cleanly, and the
   other starts — about 30 seconds end to end. The `demo` telemetry
   attribute always reports which one is live.

Remove `~/hailo-identity/` to return to separate per-demo devices.

## 6. Suggested Gauges

`person_count` 0–10 (alert marker at your threshold), `fps` 0–35 (green
`#0ca30c` ≥25, orange `#ec835a` 15–25, red `#d03b3b` <15), `cpu_temp` 0–100
(green <65, amber `#fab219` 65–75, red >75). `mode` and `top_object` as text
tiles; `objects` in a table widget.

## Known quirks

- Use camera input; file inputs can crash in the underlying pipeline's
  file-loop path.
- The pipeline apps retitle their process (e.g. `Hailo Detection App`) — use
  that name for `pgrep`/`pkill`, not the script name.
