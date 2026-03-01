# FPGA Logic Source (Generated + Patched)

This folder stores the generated FPGA logic source for the Complex-NN Accelerator, copied from a known-good build and checked in for reproducibility.

## Included

- `pre_hls_integration.tcl`
  - re-runnable AXI2AXI cleanup
- `tinyml_complex/hls_output/scripts/shls_integrate_accels.tcl`
  - COREAXI4INTERCONNECT pinned to `2.8.103`
  - re-runnable SmartDesign cleanup
- `tinyml_complex/hls_output/scripts/libero/create_hdl_plus*.tcl`
  - re-runnable HDL core handling
- `tinyml_complex/hls_output/rtl/*.v`
- `tinyml_complex/hls_output/rtl/mem_init/*.mem`

## Intended Use

Use these files as the authoritative Complex-NN Accelerator FPGA integration source for:

- rebuilding from source with consistent behavior
- avoiding script drift across Libero reruns
- archiving exactly what was used to produce the demo bitstream
