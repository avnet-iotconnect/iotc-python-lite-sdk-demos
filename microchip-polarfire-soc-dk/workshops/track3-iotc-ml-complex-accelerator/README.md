# /IOTCONNECT Complex-NN Accelerator Workshop (Track 3)

Track 3 targets stronger HW acceleration gains by combining larger compute and batched execution.

## Why This Track Exists

Track 3 is the performance-focused workshop. It demonstrates how arithmetic intensity and batching can produce clearer hardware acceleration benefits.

## What You Build and Validate

- Track 3 FPGA image programmed and package deployed
- Device connected and interactive through `/IOTCONNECT`
- `sw` and `hw` path benchmarks captured in dashboard
- speedup trend interpretation for larger batch sizes

## Project Organization

- `WORKSHOP.md`: participant runbook (self-contained)
- `developer-guide.md`: complete source rebuild flow
- `assets/fpga-job/`: prebuilt FlashPro job + timing/resource reports
- `assets/smarthls-module/tinyml_complex/`: complex accelerator source
- `src/`: runtime app and ELFs

## Artifact Provenance

- Base design source:
  - https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design/releases
- Complex accelerator source and training/export tooling are included in this track.
- Prebuilt `.job` and ELFs are included for participant quickstart.

## Runtime Binaries

- `src/runtimes/tinyml_complex.no_accel.elf`
- `src/runtimes/tinyml_complex.accel.elf`

## Participant Insight: Expected Performance

Track 3 is where HW advantage is usually most visible. For moderate/large batch, `hw_avg_time_s` should improve relative to `sw_avg_time_s` more clearly than Track 1/2.

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
3. Track dashboard template: `../templates-iotconnect/mchp-track3-dashboard-template.json`
4. Shared template/dashboard notes: `../templates-iotconnect/README.md`
5. Full rebuild flow: `developer-guide.md`
6. Cross-track technical white paper: `../tech-reference.md`
