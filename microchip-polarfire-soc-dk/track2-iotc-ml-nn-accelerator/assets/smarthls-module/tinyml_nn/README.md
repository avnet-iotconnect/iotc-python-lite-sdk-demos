# Tiny-NN SmartHLS Module

This directory contains a SmartHLS module for a small NN-style classifier (`tinyml_nn`).

## Build Outputs

Run in this directory:

```powershell
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_no_accel
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_accel
```

Expected:

- `hls_output\tinyml_nn.no_accel.elf`
- `hls_output\tinyml_nn.accel.elf`
- `hls_output\scripts\shls_integrate_accels.tcl`

## Libero Integration

Open `soc\Discovery_SoC.prjx`, set root to `MPFS_DISCOVERY_KIT`, then run:

1. `script_support/additional_configurations/smarthls/pre_hls_integration.tcl`
2. `script_support/additional_configurations/smarthls/tinyml_nn/hls_output/scripts/shls_integrate_accels.tcl`
