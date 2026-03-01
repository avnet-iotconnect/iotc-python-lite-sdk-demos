# Developer Guide: /IOTCONNECT Simple Neural Network Accelerator

This is the full source-build flow for the **Simple Neural Network Accelerator** demo.

If this is your first time in this repo, start with:

- `../README.md`

It starts from a clean `v2025.07` reference design extraction and produces:

- Libero project (`.prjx`)
- NN ELFs (`tinyml_nn.no_accel.elf`, `tinyml_nn.accel.elf`)
- FlashPro job (`MPFS_DISCOVERY_KIT.job`)

## 1. Prerequisites

- Windows host
- Libero SoC 2025.2+ installed
- SmartHLS installed with Libero
- Valid Libero/SmartHLS license

Example paths:

- `C:\Microchip\Libero_SoC_2025.2\Libero_SoC\Designer\bin\libero.exe`
- `C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat`

## 2. Fresh Source Setup

1. Download:
   - `https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design/archive/refs/tags/v2025.07.zip`
2. Extract to a short path, for example:
   - `C:\dev\MCHP\Libero25-3\polarfire-soc-discovery-kit-reference-design-2025.07`
3. Confirm top level includes:
   - `MPFS_DISCOVERY_KIT_REFERENCE_DESIGN.tcl`
   - `script_support\additional_configurations\smarthls\`

## 3. Create Base Libero Project

1. Open Libero.
2. Open Execute Script (`Ctrl+U`).
3. Run:
   - `MPFS_DISCOVERY_KIT_REFERENCE_DESIGN.tcl`

This creates the base project in the extracted tree.

If you ran with no arguments (the normal GUI flow), your project is typically:

- `MPFS_DISCOVERY\MPFS_DISCOVERY.prjx`

If you previously used a SmartHLS argument flow, you may instead have:

- `soc\Discovery_SoC.prjx`

## 4. Build Simple Neural Network ELFs (SmartHLS)

Note:

- `tinyml_nn` is a custom workshop module and is not part of the stock Microchip `v2025.07` zip.
- If `script_support\additional_configurations\smarthls\tinyml_nn\` is missing, copy it in first.

Option A (local copy from another workspace):

```powershell
Copy-Item -Recurse -Force `
  C:\dev\MCHP\polarfire-soc-discovery-kit-reference-design-2025.07\script_support\additional_configurations\smarthls\tinyml_nn `
  C:\dev\MCHP\Libero25-3\polarfire-soc-discovery-kit-reference-design-2025.07\script_support\additional_configurations\smarthls\tinyml_nn
```

Option B (download module from GitHub zip):

```powershell
powershell -ExecutionPolicy Bypass -File `
  C:\dev\MCHP\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\ml-simple-nn-accelerator\tools\fetch-tinyml-nn-module.ps1 `
  -ReferenceDesignRoot C:\dev\MCHP\Libero25-3\polarfire-soc-discovery-kit-reference-design-2025.07 `
  -RepoZipUrl "https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/archive/refs/heads/polarfire-workshop.zip"
```

Important:

- The branch/tag in `RepoZipUrl` must already contain:
  - `microchip-polarfire-soc-dk/ml-simple-nn-accelerator/assets/smarthls-module/tinyml_nn`

Option C (use local module path, no GitHub dependency):

```powershell
powershell -ExecutionPolicy Bypass -File `
  C:\dev\MCHP\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\ml-simple-nn-accelerator\tools\fetch-tinyml-nn-module.ps1 `
  -ReferenceDesignRoot C:\dev\MCHP\Libero25-3\polarfire-soc-discovery-kit-reference-design-2025.07 `
  -LocalModulePath C:\dev\MCHP\iotc-python-lite-sdk-demos\microchip-polarfire-soc-dk\ml-simple-nn-accelerator\assets\smarthls-module\tinyml_nn
```

If you prefer `wget` syntax in PowerShell, this works too (`wget` maps to `Invoke-WebRequest`):

```powershell
wget "https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/archive/refs/heads/polarfire-workshop.zip" -OutFile "$env:TEMP\iotc-python-lite-sdk-demos-polarfire-workshop.zip"
```

Run from:

- `script_support\additional_configurations\smarthls\tinyml_nn\`

Commands:

```powershell
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_no_accel
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_accel
```

Expected outputs:

- `hls_output\tinyml_nn.no_accel.elf`
- `hls_output\tinyml_nn.accel.elf`
- `hls_output\scripts\shls_integrate_accels.tcl`

## 4.1 Use Checked-In FPGA Integration Source (Recommended)

This workshop includes generated + patched integration source in:

- `assets/fpga-source/pre_hls_integration.tcl`
- `assets/fpga-source/tinyml_nn/hls_output/scripts/...`
- `assets/fpga-source/tinyml_nn/hls_output/rtl/...`

Copy these into your extracted reference-design tree before script execution in Step 6.

```powershell
Copy-Item -Force `
  <WORKSHOP_ROOT>\assets\fpga-source\pre_hls_integration.tcl `
  <REFERENCE_DESIGN_ROOT>\script_support\additional_configurations\smarthls\

Copy-Item -Recurse -Force `
  <WORKSHOP_ROOT>\assets\fpga-source\tinyml_nn\hls_output\scripts `
  <REFERENCE_DESIGN_ROOT>\script_support\additional_configurations\smarthls\tinyml_nn\hls_output\
```

## 5. Open SmartHLS Libero Project

Open whichever project was created in Step 3:

- `MPFS_DISCOVERY\MPFS_DISCOVERY.prjx` (most common)
- or `soc\Discovery_SoC.prjx`

Set root in Design Hierarchy to:

- `MPFS_DISCOVERY_KIT`

## 6. Integrate Simple Neural Network Accelerator

In Libero, use `Project -> Execute Script` (or `Ctrl+U`), then use `...` browse to pick each script.

If you are not using the checked-in `assets/fpga-source` scripts, pin the generated AXI core version to match the base design:

- edit `.../tinyml_nn/hls_output/scripts/shls_integrate_accels.tcl`
- replace `COREAXI4INTERCONNECT:2.9.100` with `COREAXI4INTERCONNECT:2.8.103`

PowerShell helper:

```powershell
$fp="C:\dev\MCHP\Libero25-3\polarfire-soc-discovery-kit-reference-design-2025.07\script_support\additional_configurations\smarthls\tinyml_nn\hls_output\scripts\shls_integrate_accels.tcl"
(Get-Content $fp) -replace 'COREAXI4INTERCONNECT:2\.9\.100','COREAXI4INTERCONNECT:2.8.103' | Set-Content $fp
```

Run in this order:

1. `C:/dev/MCHP/Libero25-3/polarfire-soc-discovery-kit-reference-design-2025.07/script_support/additional_configurations/smarthls/pre_hls_integration.tcl`
2. `C:/dev/MCHP/Libero25-3/polarfire-soc-discovery-kit-reference-design-2025.07/script_support/additional_configurations/smarthls/tinyml_nn/hls_output/scripts/shls_integrate_accels.tcl`

Why absolute paths:

- Libero script working directory is not always the repo root.
- Relative paths can fail even when files exist.

If your extracted folder is different, replace the `C:/dev/MCHP/Libero25-3/...` prefix with your actual root path.

Important:

- Run these once on a clean project.
- If you get `already exists` core/instance errors, clean and restart from fresh extraction.

## 7. Build FPGA Programming Data

Run Libero flow:

1. `SYNTHESIZE`
2. `PLACEROUTE`
3. `VERIFYTIMING`
4. `GENERATEPROGRAMMINGDATA`

Then export FlashPro job.

Expected output:

- `soc\designer\MPFS_DISCOVERY_KIT\export\MPFS_DISCOVERY_KIT.job`

## 8. Publish Workshop Artifacts

Copy these into the demo folder:

- Job:
  - `ml-simple-nn-accelerator\assets\fpga-job\MPFS_DISCOVERY_KIT.job`
- ELFs:
  - `ml-simple-nn-accelerator\src\runtimes\tinyml_nn.no_accel.elf`
  - `ml-simple-nn-accelerator\src\runtimes\tinyml_nn.accel.elf`

## 9. Build Package

From:

- `ml-simple-nn-accelerator\`

```bash
bash ./create-package.sh
```

Output:

- `package.tar.gz`

## 10. Sanity Validation

After programming board and deploying package:

```text
classify sw 2 11
classify hw 2 11
bench both 2 11 1000
```

Expected:

- valid `pred` and score telemetry
- `ml_classify` and `ml_bench` events
- async bench state via `job_state`

## 11. Known Failure Modes

- `Please select a root`:
  - set root to `MPFS_DISCOVERY_KIT` before integration script execution.
- `Your design contains multiple versions of the same core`:
  - cause in this flow is usually `HLS_AXI4Interconnect` generated as `COREAXI4INTERCONNECT:2.9.100` while base design uses `2.8.103`.
  - fix before integration by editing:
    - `script_support/additional_configurations/smarthls/tinyml_nn/hls_output/scripts/shls_integrate_accels.tcl`
  - replace:
    - `COREAXI4INTERCONNECT:2.9.100`
  - with:
    - `COREAXI4INTERCONNECT:2.8.103`
  - then rerun integration on a clean project.
- `core already exists` / `instance already exists`:
  - clean and restart from a fresh extraction.
- ELF permission errors on board:
  - `chmod +x /home/weston/demo/runtimes/*.elf`
