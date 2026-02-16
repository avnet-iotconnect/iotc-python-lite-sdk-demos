# /IOTCONNECT Tiny-NN Accelerator Workshop (Track 2)

Track 2 introduces a compact fixed-point neural-network accelerator while preserving the same `/IOTCONNECT` command interface used in Track 1.

## Why This Track Exists

Track 2 is the transition from deterministic baseline classification to a true NN-style accelerator flow.

It is intended to teach:

- how NN kernels map into the same cloud command contract
- how to evaluate SW/HW parity and benchmark behavior
- how SmartHLS + Libero artifacts tie to runtime outputs

## What You Build and Validate

- Track 2 job programmed and app deployed
- Device operational in `/IOTCONNECT`
- NN inference running in `sw` and `hw`
- Benchmark telemetry available for interpretation

## Project Organization

- `WORKSHOP.md`: participant runbook (self-contained)
- `developer-guide.md`: full SmartHLS + Libero flow
- `assets/fpga-job/`: prebuilt FlashPro job + reports
- `assets/smarthls-module/tinyml_nn/`: NN accelerator source
- `src/`: runtime app, install script, and ELFs

## Artifact Provenance

- Base design source:
  - https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design/releases
- Track module and integration collateral are included in this repo.
- Prebuilt `.job` and ELFs are included for participant quickstart.

## Runtime Binaries

- `src/runtimes/tinyml_nn.no_accel.elf`
- `src/runtimes/tinyml_nn.accel.elf`

## Participant Insight: Expected Performance

Track 2 often shows modest HW gains when workload size and batch are large enough to offset acceleration overhead. It is a realism step between Track 1 and Track 3.

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
3. Track dashboard template: `../templates-iotconnect/mchp-track2-dashboard-template.json`
4. Shared template/dashboard notes: `../templates-iotconnect/README.md`
5. Full rebuild flow: `developer-guide.md`
6. Cross-track technical white paper: `../tech-reference.md`
