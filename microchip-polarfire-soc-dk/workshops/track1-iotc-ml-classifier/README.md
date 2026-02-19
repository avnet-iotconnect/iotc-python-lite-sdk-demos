# /IOTCONNECT ML Classifier Workshop (Track 1)

Track 1 is the baseline workshop for validating end-to-end cloud command/control and telemetry on PolarFire SoC.

## Why This Track Exists

Track 1 gives you the fastest path to confirm the complete loop works:

- board programming
- `/IOTCONNECT` onboarding
- command execution from cloud
- telemetry returned from device

It uses a deterministic template-correlation style classifier so parity and reproducibility are easy to verify.

## What You Build and Validate

- Device connected to `/IOTCONNECT`
- App responding to `classify` and `bench`
- Dashboard showing classification and benchmark telemetry
- SW/HW comparison baseline for later tracks

## Project Organization

- `WORKSHOP.md`: participant runbook (self-contained)
- `developer-guide.md`: full source regeneration flow
- `assets/fpga-job/`: prebuilt FlashPro `.job` and implementation reports
- `assets/smarthls-module/`: SmartHLS accelerator source
- `src/`: runtime Python app, installer, and runtime ELFs

## Artifact Provenance

- Base reference design source:
  - https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design/releases
- SmartHLS + Libero flow produces:
  - FPGA job (`MPFS_DISCOVERY_KIT.job`)
  - SW/HW runtime ELFs
- Prebuilt artifacts are included for participant quickstart.

## Runtime Binaries

- `src/runtimes/invert_and_threshold.no_accel.elf`
- `src/runtimes/invert_and_threshold.accel.elf`

## Participant Insight: Expected Performance

For very small workloads, SW can be close to or faster than HW due to offload/setup overhead. This track intentionally demonstrates that baseline behavior.

## Command Contract Used in This Track

- `classify <mode> <class|random> <seed|random> [batch]`
- `bench <mode> <class|random> <seed|random> <batch>` or `bench random [batch]`
- `status <basic|full|include_leds=true|include_leds=false>`
- `led ...`, `leds ...`
- `load ...`
- `file-download <url>`

## Start Points

1. Participant flow: `WORKSHOP.md`
2. Device template (all tracks): `../templates-iotconnect/microchip-polarfire-tinyml-template.json`
3. Track dashboard template: `../templates-iotconnect/mchp-track1-dashboard-template.json`
4. Shared template/dashboard notes: `../templates-iotconnect/README.md`
5. Full rebuild flow: `developer-guide.md`
6. Cross-track technical white paper: `../tech-reference.md`
