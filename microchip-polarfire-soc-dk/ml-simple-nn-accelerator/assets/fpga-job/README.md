# FPGA Job (Required)

Place the neural network workshop FlashPro job file here:

- `MPFS_DISCOVERY_KIT.job`

SHA256:

- `2EA1CB030E957219FDF9A498F6B6F51F81064C80FC043778B2A6391E140E418B`

This job must match the Simple Neural Network accelerator build used to produce:

- `src/runtimes/tinyml_nn.accel.elf`
- `src/runtimes/tinyml_nn.no_accel.elf`

Build and export steps are documented in:

- `../../developer-guide.md`

## Implementation Reports

Implementation/timing/utilization reports are included under:

- `reports/`

Key files:

- `reports/MPFS_DISCOVERY_KIT_compile_netlist_resources.rpt`
- `reports/MPFS_DISCOVERY_KIT_compile_netlist_hier_resources.csv`
- `reports/MPFS_DISCOVERY_KIT_iteration_summary.rpt`
- `reports/MPFS_DISCOVERY_KIT_timing_*.rpt`
- `reports/MPFS_DISCOVERY_KIT_timing_violations_*.rpt`
- `reports/place_and_route_jitter_report.txt`

