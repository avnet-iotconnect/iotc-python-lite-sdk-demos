# /IOTCONNECT + PolarFire SoC ML Classifier Workshop

## Goal

Run a prebuilt Tiny-ML workload on PolarFire SoC and control it from /IOTCONNECT commands.

Students do **not** need Libero or SmartHLS.

## Tool Downloads

Student programming tool (FlashPro Express v11.6):

- [FlashPro and FlashPro Express v11.6 Release Notes](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ProductDocuments/ReleaseNotes/flashpro_v11_6_release_notes.pdf)
- [FlashPro and FlashPro Express v11.6 for Windows](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/media-content/FPGA/v11.6/FlashPro_v11.6.exe)
- [FlashPro and FlashPro Express v11.6 for Linux](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/media-content/FPGA/v11.6/FlashProExpressStandalone_v11_6Linux.tar)

Instructor-only tools:

- Libero SoC + SmartHLS (needed only to regenerate FPGA design and ELFs).

## What Is Prebuilt

- FPGA fabric is precompiled and delivered as a `.job` file.
- Runtime ELFs are prebuilt and included in `src/runtimes/`.
- Python cloud app is prebuilt in this workshop package.
- Linux SD card image is preloaded by instructor before the workshop.

## Directory Layout

```text
iotconnect-ml-classifier-workshop/
  assets/
    fpga-job/
      MPFS_DISCOVERY_KIT.job
  create-package.sh
  package.tar.gz
  README.md
  WORKSHOP.md
  src/
    app.py
    ml_runner.py
    install.sh
    runtimes/
      invert_and_threshold.no_accel.elf
      invert_and_threshold.accel.elf
      README.md
```

## Instructor Procedure

1. Program board with `assets/fpga-job/MPFS_DISCOVERY_KIT.job` in FlashPro/Program Debug.
2. Build package from this directory:
   ```bash
   bash ./create-package.sh
   ```
3. Distribute to students:
   - FPGA `.job`
   - workshop `package.tar.gz`
   - device onboarding config files

Linux image reference (for instructor prep only):

- `https://github.com/linux4microchip/meta-mchp/releases`
- Students do not need to flash Linux during workshop if SD cards are preloaded.

## Student Procedure

1. Program board using provided `.job`.
2. Boot Linux and login as `root`.
3. Put `package.tar.gz` on board.
4. Install and run:
   ```bash
   mkdir -p /home/weston/demo
   cd /home/weston/demo
   tar -xzf package.tar.gz --overwrite
   bash ./install.sh
   python3 app.py
   ```

## Package Transfer (HTTP Fallback)

Use this if `scp` fails (e.g., corrupted MAC).

On Windows host:

```powershell
cd C:\dev\MCHP\Libero25-2\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\iotconnect-ml-classifier-workshop
python -m http.server 8000
```

On board:

```bash
cd /root
wget http://<HOST_IP>:8000/package.tar.gz -O /root/package.tar.gz
cp /root/package.tar.gz /home/weston/demo/
```

## Command Reference

All commands are entered as a single space-delimited string in /IOTCONNECT.

### `classify`

```text
classify <mode> <class> <seed> [batch]
```

Examples:

- `classify hw 2 11`
- `classify sw 2 11 1000`

Rules:

- `mode`: `hw|sw`
- `class`: `0..5`
- `batch`: `1..10000`

### `bench`

```text
bench <mode> <class> <seed> <batch>
```

Examples:

- `bench both 2 11 1000`
- `bench hw 2 11 1000`
- `bench sw 2 11 1000`

Rules:

- `mode`: `both|hw|sw`
- runs asynchronously
- emits `job_state started` and `job_state done`
- if a heavy job is running, new heavy jobs return `Busy running: <job>`

### `status`

Examples:

- `status`
- `status include_leds=true`

Periodic status telemetry is automatically sent every 15 seconds.

### `led` and `leds`

Compact 8-visible-LED control:

- `led` (report current `leds` bitstring)
- `led 11111111` (all visible LEDs on)
- `leds 10100101` (direct bitstring set alias)

Indexed control:

- `led set 0 on`
- `led set 0 off`
- `led set 0 toggle`

Patterns:

- `led pattern blink 12 100`
- `led pattern chase 24 80`
- `led pattern alternate 20 120`
- `led stop`

### `load`

Background CPU load generator:

- `load status`
- `load start 2 80`
- `load start 4 95`
- `load stop`

Rules:

- workers: `1..8`
- duty: `1..100`

### `file-download`

```text
file-download <url-to-package.tar.gz>
```

Downloads a new workshop package, installs it, and restarts `app.py`.

## Recommended Demo Flow

1. `status`
2. `led 11111111`
3. `led 00000000`
4. `classify hw 2 11 1000`
5. `classify sw 2 11 1000`
6. `load start 2 80`
7. `bench both 2 11 1000`
8. wait for `job_state done`
9. `load stop`
10. `bench both 2 11 1000`

## Expected Telemetry Events

- `heartbeat`
- `device_status`
- `ml_classify` / `ml_classify_batch`
- `ml_bench`
- `led_state`
- `load_state`
- `job_state`

## Troubleshooting

### `Permission denied` for `.elf`

```bash
chmod +x /home/weston/demo/runtimes/*.elf 2>/dev/null || true
chmod +x /root/runtimes/*.elf 2>/dev/null || true
```

Restart app:

```bash
cd /home/weston/demo
python3 app.py
```

### `Received C2D message Refresh Attribute from backend`

This is a backend refresh event, not a hardware failure.  
Restart app to reinitialize cleanly:

```bash
pkill -f app.py || true
cd /home/weston/demo
python3 app.py
```

### MQTT keepalive timeout during long jobs

- Keep load moderate (`load start 2 80` first).
- Use async bench/classify as implemented.
- Wait for `job_state done` before launching another heavy command.
