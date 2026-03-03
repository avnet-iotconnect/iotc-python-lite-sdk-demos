open_project -file {hls_output/soc/Icicle_SoC.prjx}
source hls_output/scripts/shls_integrate_accels.tcl
close_project -save 1
