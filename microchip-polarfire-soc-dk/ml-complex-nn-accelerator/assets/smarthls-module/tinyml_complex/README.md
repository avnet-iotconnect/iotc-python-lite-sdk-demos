# tinyml_complex SmartHLS Module (Complex Neural Network Accelerator)

This is a starter SmartHLS module for the Complex Neural Network Accelerator demo.

Contents:

- `Makefile`
- `Makefile.user`
- `config.tcl`
- `main_variations/main.fifo.cpp`

## Purpose

This starter increases model compute versus simpler demos by using:

- richer feature extraction
- two hidden layers
- deterministic generated weights (for repeatable builds)

It is intended as a baseline scaffold before replacing with a trained model path.

## Prebuilt HLS Output

The compiled HLS output artifacts are available for download from S3:

- [tinyml_complex.RISCV.src](https://s3.us-east-1.amazonaws.com/avnetpublicaccess/large-repo-files/tinyml_complex.RISCV.src)
- [tinyml_complex.src](https://s3.us-east-1.amazonaws.com/avnetpublicaccess/large-repo-files/tinyml_complex.src)

## Build

From this folder inside the reference design tree:

```powershell
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_no_accel
& "C:\Microchip\Libero_SoC_2025.2\SmartHLS\SmartHLS\bin\shls.bat" -a soc_sw_compile_accel
```
