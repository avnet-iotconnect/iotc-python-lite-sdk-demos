# Developer Guide: /IOTCONNECT Complex-NN Accelerator Workshop (Track 3)

This guide is the source-build path for generating:

- FPGA job: `MPFS_DISCOVERY_KIT.job`
- software ELF: `tinyml_complex.no_accel.elf`
- hardware ELF: `tinyml_complex.accel.elf`

If this is your first time in this repo, start with:

- `../README.md`

## 1. Base Reference Design

1. Download Microchip reference design `v2025.07`.
2. Extract to a clean path.
3. Open Libero and run:
   - `Project -> Execute Script`
   - select `MPFS_DISCOVERY_KIT_REFERENCE_DESIGN.tcl`

## 2. Add Complex SmartHLS Module (Track 3)

Copy the Track 3 SmartHLS module into:

- `script_support/additional_configurations/smarthls/tinyml_complex/`

PowerShell example:

```powershell
Copy-Item -Recurse -Force `
  C:\dev\MCHP\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\workshops\track3-iotc-ml-complex-accelerator\assets\smarthls-module\tinyml_complex `
  C:\dev\MCHP\polarfire-soc-discovery-kit-reference-design-2025.07\script_support\additional_configurations\smarthls\
```

Required files in that module:

- `Makefile`
- `Makefile.user`
- `config.tcl`
- `main_variations/main.fifo.cpp`

## 3. Build ELFs with SmartHLS

Run from:

- `script_support/additional_configurations/smarthls/tinyml_complex/`

Before compiling, generate/update trained model weights header:

```powershell
python C:\dev\MCHP\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\workshops\track3-iotc-ml-complex-accelerator\tools\train_and_export_complex.py
Copy-Item -Force `
  C:\dev\MCHP\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\workshops\track3-iotc-ml-complex-accelerator\assets\smarthls-module\tinyml_complex\main_variations\model_weights.h `
  <REFERENCE_DESIGN_ROOT>\script_support\additional_configurations\smarthls\tinyml_complex\main_variations\
```

Commands:

```powershell
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_no_accel
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_accel
```

Expected outputs:

- `hls_output/tinyml_complex.no_accel.elf`
- `hls_output/tinyml_complex.accel.elf`

## 3.1 Use Checked-In FPGA Integration Source (Recommended)

This workshop includes generated + patched FPGA integration source in:

- `assets/fpga-source/pre_hls_integration.tcl`
- `assets/fpga-source/tinyml_complex/hls_output/scripts/...`
- `assets/fpga-source/tinyml_complex/hls_output/rtl/...`

These files already include the fixes we validated:

- COREAXI4INTERCONNECT aligned to `2.8.103`
- re-runnable cleanup for AXI2AXI and HDL cores

Copy these into your reference-design tree after SmartHLS build:

```powershell
Copy-Item -Force `
  C:\dev\MCHP\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\workshops\track3-iotc-ml-complex-accelerator\assets\fpga-source\pre_hls_integration.tcl `
  <REFERENCE_DESIGN_ROOT>\script_support\additional_configurations\smarthls\

Copy-Item -Recurse -Force `
  C:\dev\MCHP\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\workshops\track3-iotc-ml-complex-accelerator\assets\fpga-source\tinyml_complex\hls_output\scripts `
  <REFERENCE_DESIGN_ROOT>\script_support\additional_configurations\smarthls\tinyml_complex\hls_output\
```

## 4. Integrate Accelerator in Libero

In Libero use `Project -> Execute Script` and run in order:

1. `script_support/additional_configurations/smarthls/pre_hls_integration.tcl`
2. `script_support/additional_configurations/smarthls/tinyml_complex/hls_output/scripts/shls_integrate_accels.tcl`

If core-version mismatch warning appears, resolve to a single core version before running synthesis/P&R.

## 5. Build and Export Job

Run design flow:

- Synthesize
- Place and Route
- Verify Timing
- Generate Bitstream
- Export Programming File (`.job`)

## 6. Stage Workshop Artifacts

Copy into this workshop folder:

- job file -> `assets/fpga-job/MPFS_DISCOVERY_KIT.job`
- ELFs -> `src/runtimes/`
  - `tinyml_complex.no_accel.elf`
  - `tinyml_complex.accel.elf`

Optional integrity check (PowerShell):

```powershell
Get-FileHash .\src\runtimes\tinyml_complex.no_accel.elf
Get-FileHash .\src\runtimes\tinyml_complex.accel.elf
```

Current reference hashes in this repo:

- `tinyml_complex.no_accel.elf`: `B6997E5E412BCD06707B7DB1B7A4CFAAA756A6CD3FA158774F3124EE8BC7A059`
- `tinyml_complex.accel.elf`: `9D17F0ED4A01B2BC2A4DE3CA2ED2D8013931BA11B638BBD036A672E78A4E0D8D`

## 7. Build Quickstart Package

```bash
bash ./create-package.sh
```

Produces:

- `package.tar.gz`
