# /IOTCONNECT ML Classifier Workshop

This directory is self-contained.  
All workshop source, runtime binaries, package scripts, and documentation are here.

- Full lab manual: `WORKSHOP.md`
- App source: `src/app.py`
- Runtime launcher: `src/ml_runner.py`
- Prebuilt ELFs: `src/runtimes/`
- Prebuilt FPGA job: `assets/fpga-job/MPFS_DISCOVERY_KIT.job`
- Package script: `create-package.sh`

Linux image reference (for instructor prep only):

- `https://github.com/linux4microchip/meta-mchp/releases`
- In this workshop, the SD card is preloaded before class.

## Tool Links

Student programming tool (FlashPro Express v11.6):

- [FlashPro and FlashPro Express v11.6 Release Notes](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ProductDocuments/ReleaseNotes/flashpro_v11_6_release_notes.pdf)
- [FlashPro and FlashPro Express v11.6 for Windows](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/media-content/FPGA/v11.6/FlashPro_v11.6.exe)
- [FlashPro and FlashPro Express v11.6 for Linux](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/media-content/FPGA/v11.6/FlashProExpressStandalone_v11_6Linux.tar)

Instructor build tools:

- Libero SoC + SmartHLS are required only for rebuilding fabric/ELFs.
- Students do not need Libero in this workshop flow.

## Build Package

From this folder:

```bash
bash ./create-package.sh
```

Output:

- `package.tar.gz` (in this folder only)

## Deploy To Board

On board:

```bash
mkdir -p /home/weston/demo
cd /home/weston/demo
tar -xzf package.tar.gz --overwrite
bash ./install.sh
python3 app.py
```

## Command Quick Reference

Use space-delimited command strings in /IOTCONNECT.

### Classify

```text
classify hw 2 11
classify sw 2 11 1000
```

Args:

- `mode`: `hw` or `sw`
- `class`: `0..5`
- `seed`: integer
- `batch` (optional): `1..10000`

### Bench

```text
bench both 2 11 1000
bench hw 2 11 1000
bench sw 2 11 1000
```

Notes:

- Bench runs asynchronously.
- Telemetry includes `job_state: started|done`.
- While bench runs, new heavy jobs return `Busy running: bench`.

### Device Status

```text
status
status include_leds=true
```

Status is also published automatically every 15 seconds.

### LED Control

```text
led
led 11111111
leds 10100101
led set 0 on
led set 0 off
led pattern blink 12 100
led pattern chase 24 80
led pattern alternate 20 120
led stop
```

`leds` is an 8-bit visible LED state string (`1=on`, `0=off`).

### CPU Load Generator

```text
load status
load start 2 80
load start 4 95
load stop
```

Args:

- `workers`: `1..8`
- `duty`: `1..100` (%)

### Package Update Command

```text
file-download <url-to-package.tar.gz>
```

This downloads a new package, installs it, and restarts `app.py`.
