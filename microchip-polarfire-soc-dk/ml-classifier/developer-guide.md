# Developer Guide: /IOTCONNECT Machine Learning Classifier

This guide is the full developer procedure to regenerate the Machine Learning classifier FPGA `.job` and runtime ELFs from a clean reference design checkout.

If this is your first time in this repo, start with:

- `../README.md`

## 1. Scope

This flow builds:

- base Libero project (`.prjx`)
- SmartHLS accelerator integration
- new FPGA programming job (`.job`)
- updated runtime ELFs (`invert_and_threshold.accel.elf`, `invert_and_threshold.no_accel.elf`)

Quickstart flow does not run this path. Quickstart flow uses prebuilt artifacts.

## 2. Host Prerequisites

- Windows host
- Libero SoC 2025.2+ installed
- SmartHLS installed with Libero
- Valid Libero/SmartHLS license
- FlashPro Express for programming

Example tool paths:

- `C:\Microchip\Libero_SoC_2025.2\Libero_SoC\Designer\bin\libero.exe`
- `C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat`

## 3. Start From Fresh Reference Design

1. Download:
   - `https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design/archive/refs/tags/v2025.07.zip`
2. Extract to a short path, for example:
   - `C:\dev\MCHP\Libero25-3\polarfire-soc-discovery-kit-reference-design-2025.07`
3. Confirm top-level files exist:
   - `MPFS_DISCOVERY_KIT_REFERENCE_DESIGN.tcl`
   - `script_support\`

## 4. Create Base Libero Project (`.prjx`)

1. Open Libero.
2. Open Execute Script (`Ctrl+U`).
3. Execute:
   - `MPFS_DISCOVERY_KIT_REFERENCE_DESIGN.tcl`
4. This creates/open the base project under:
   - `MPFS_DISCOVERY\MPFS_DISCOVERY.prjx` (base flow)
   - or `soc\Discovery_SoC.prjx` (SmartHLS flow once integrated)

Notes:

- This step alone builds the reference project structure.
- SmartHLS accelerator is not integrated yet.

## 5. Build SmartHLS ELFs

Run from:

- `script_support\additional_configurations\smarthls\invert_and_threshold\`

Commands:

```powershell
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_no_accel
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_accel
```

Expected outputs:

- `hls_output\invert_and_threshold.no_accel.elf`
- `hls_output\invert_and_threshold.accel.elf`
- `hls_output\scripts\shls_integrate_accels.tcl`

## 5.1 Use Checked-In FPGA Integration Source (Recommended)

This workshop includes generated + patched integration source in:

- `assets/fpga-source/pre_hls_integration.tcl`
- `assets/fpga-source/invert_and_threshold/hls_output/scripts/...`
- `assets/fpga-source/invert_and_threshold/hls_output/rtl/...`

Copy these into your extracted reference-design tree before script execution in Step 6.

```powershell
Copy-Item -Force `
  <WORKSHOP_ROOT>\assets\fpga-source\pre_hls_integration.tcl `
  <REFERENCE_DESIGN_ROOT>\script_support\additional_configurations\smarthls\

Copy-Item -Recurse -Force `
  <WORKSHOP_ROOT>\assets\fpga-source\invert_and_threshold\hls_output\scripts `
  <REFERENCE_DESIGN_ROOT>\script_support\additional_configurations\smarthls\invert_and_threshold\hls_output\
```

## 6. Integrate Accelerator In Libero

Open the SmartHLS project (if not already open):

- `soc\Discovery_SoC.prjx`

Set root before integration:

- In Design Hierarchy, set root to `MPFS_DISCOVERY_KIT`.

Execute scripts in this order:

Use `Project -> Execute Script` (or `Ctrl+U`), then browse to each script.

1. `C:/dev/MCHP/Libero25-3/polarfire-soc-discovery-kit-reference-design-2025.07/script_support/additional_configurations/smarthls/pre_hls_integration.tcl`
2. `C:/dev/MCHP/Libero25-3/polarfire-soc-discovery-kit-reference-design-2025.07/script_support/additional_configurations/smarthls/invert_and_threshold/hls_output/scripts/shls_integrate_accels.tcl`

Why absolute paths:

- Libero script working directory is not always the repo root.
- Relative paths can fail even when files exist.

If your extracted folder is different, replace the `C:/dev/MCHP/Libero25-3/...` prefix with your actual root path.

Important:

- Run integration scripts once per clean project.
- If you see `already exists` core/instance errors, clean project artifacts and restart from fresh extraction.

## 7. Build Bitstream and Export Job

In Libero Design Flow:

1. `SYNTHESIZE`
2. `PLACEROUTE`
3. `VERIFYTIMING`
4. `GENERATEPROGRAMMINGDATA`
5. Export FlashPro job

Expected job location:

- `soc\designer\MPFS_DISCOVERY_KIT\export\MPFS_DISCOVERY_KIT.job`

## 8. Publish Workshop Artifacts

Copy generated artifacts into workshop folder:

- FPGA job:
  - `ml-classifier\assets\fpga-job\MPFS_DISCOVERY_KIT.job`
- ELFs:
  - `ml-classifier\src\runtimes\invert_and_threshold.no_accel.elf`
  - `ml-classifier\src\runtimes\invert_and_threshold.accel.elf`

Then build package:

```bash
bash ./create-package.sh
```

## 9. Quick Validation

After programming board and deploying package:

```text
classify sw 2 11
classify hw 2 11
bench both 2 11 1000
```

Expected:

- deterministic predictions for same class/seed
- `ml_classify` and `ml_bench` telemetry
- async job state for bench (`started`, `done`)

## 10. Common Pitfalls

- `Please select a root`:
  - set root to `MPFS_DISCOVERY_KIT` before running integration scripts.
- `core already exists` / `instance already exists`:
  - project not clean; restart from fresh extracted source.
- `run_on_board` unrecognized:
  - use supported SmartHLS targets (`soc_sw_compile_*`, `soc_accel_proj_run`) or workshop scripts.
- ELF permission denied on board:
  - `chmod +x ./runtimes/*.elf`.
