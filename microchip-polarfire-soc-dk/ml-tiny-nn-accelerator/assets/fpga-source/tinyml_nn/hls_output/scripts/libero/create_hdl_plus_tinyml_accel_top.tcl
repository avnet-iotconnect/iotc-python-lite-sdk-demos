
# This Tcl file will import SmartHLS generated Verilog and create an HDL+ core for the top-level module tinyml_accel_top in Libero.
# You can easily instantiate the HDL+ core in a SmartDesign.
# It will create a bus interface for AXI4 Initiator/Target if the top-level module uses them.
# It will also group pins into AXI4 Master/Slave/Stream interfaces if they match the AXI specification.
# See the SmartHLS User Guide for more information about the AXI4 interfaces.
#
# How to use this Tcl file:
#   1. Open a project in Libero.
#   2. Click "Project" tab on the top left corner and click "Execute Script"
#       OR  press "Ctrl+U".
#   3. Click "..." to browse into the folder containing the SmartHLS project and select this Tcl file
#       OR  enter the full path of this Tcl file.
#       Note: The path is printed in the terminal as SmartHLS runs.
#             e.g. Info: Generating HDL+ Tcl script to be imported in SmartDesign: <full path>.
#   4. Click "Run".
#   5. Go to "Design Flow" tab on the middle left and click "Create Design" -> "Create SmartDesign"
#      (skip this step if there's an existing SmartDesign).
#   6. Go to "Design Hierarchy" tab next to "Design Flow" tab, find the HDL+ core named as "<top module name>_top",
#      and drag it into the SmartDesign or right click and select "instantiate in <SmartDesign name>".

# Find the absolute path to the HLS generated RTL folder.
# hlsPrjAbsPath contains the absolute path to the SmartHLS project directory.
set hlsPrjAbsPath [file normalize [file dirname [info script]]/../../..]
set srcFiles [concat \
    $hlsPrjAbsPath/hls_output/rtl/tinyml_nn_tinyml_accel.v \
    [glob -nocomplain $hlsPrjAbsPath/hls_output/rtl/ram_primitives/*.v] \
]


# Iterate over the sources and create_links for each file.
foreach srcFile $srcFiles {
    create_links -hdl_source $srcFile
}

# Hierarchy rebuild is required after linking the HLS generated RTL source files.
build_design_hierarchy

# Tell synthesis where to find the .mem files.
set cmd "configure_tool -name {SYNTHESIZE} \
   -params {SYNPLIFY_OPTIONS:set_option -hdl_define -set MEM_INIT_DIR=\"$hlsPrjAbsPath/hls_output/rtl/mem_init/\"}"
puts "$cmd"
eval $cmd


# Make script re-runnable.
# Remove stale HDL core definition if this script is re-run.
catch {remove_hdl_core -hdl_core_name {tinyml_accel_top}}

# If the HDL+ core already exists, keep it and continue.
set _create_rc [catch {
    create_hdl_core \
        -file "$hlsPrjAbsPath/hls_output/rtl/tinyml_nn_tinyml_accel.v" \
        -module {tinyml_accel_top} \
        -library {work}
} _create_msg]
if {$_create_rc} {
    if {[string first "already exists" $_create_msg] < 0} {
        error $_create_msg
    }
}
#Add bus interface for AXI4 Target.
hdl_core_add_bif -hdl_core_name {tinyml_accel_top} -bif_definition {AXI4:AMBA:AMBA4:slave} -bif_name {axi4target} -signal_map {}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARADDR} -core_signal_name {axi4target_araddr}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARBURST} -core_signal_name {axi4target_arburst}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARCACHE} -core_signal_name {axi4target_arcache}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARID} -core_signal_name {axi4target_arid}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARLEN} -core_signal_name {axi4target_arlen}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARLOCK} -core_signal_name {axi4target_arlock}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARPROT} -core_signal_name {axi4target_arprot}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARQOS} -core_signal_name {axi4target_arqos}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARREADY} -core_signal_name {axi4target_arready}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARREGION} -core_signal_name {axi4target_arregion}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARSIZE} -core_signal_name {axi4target_arsize}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARUSER} -core_signal_name {axi4target_aruser}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {ARVALID} -core_signal_name {axi4target_arvalid}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {RDATA} -core_signal_name {axi4target_rdata}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {RID} -core_signal_name {axi4target_rid}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {RLAST} -core_signal_name {axi4target_rlast}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {RREADY} -core_signal_name {axi4target_rready}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {RRESP} -core_signal_name {axi4target_rresp}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {RUSER} -core_signal_name {axi4target_ruser}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {RVALID} -core_signal_name {axi4target_rvalid}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWADDR} -core_signal_name {axi4target_awaddr}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWBURST} -core_signal_name {axi4target_awburst}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWCACHE} -core_signal_name {axi4target_awcache}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWID} -core_signal_name {axi4target_awid}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWLEN} -core_signal_name {axi4target_awlen}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWLOCK} -core_signal_name {axi4target_awlock}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWPROT} -core_signal_name {axi4target_awprot}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWQOS} -core_signal_name {axi4target_awqos}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWREADY} -core_signal_name {axi4target_awready}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWREGION} -core_signal_name {axi4target_awregion}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWSIZE} -core_signal_name {axi4target_awsize}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWUSER} -core_signal_name {axi4target_awuser}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {AWVALID} -core_signal_name {axi4target_awvalid}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {WDATA} -core_signal_name {axi4target_wdata}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {WLAST} -core_signal_name {axi4target_wlast}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {WREADY} -core_signal_name {axi4target_wready}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {WSTRB} -core_signal_name {axi4target_wstrb}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {WUSER} -core_signal_name {axi4target_wuser}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {WVALID} -core_signal_name {axi4target_wvalid}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {BID} -core_signal_name {axi4target_bid}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {BREADY} -core_signal_name {axi4target_bready}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {BRESP} -core_signal_name {axi4target_bresp}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {BUSER} -core_signal_name {axi4target_buser}
hdl_core_assign_bif_signal -hdl_core_name {tinyml_accel_top} -bif_name {axi4target} -bif_signal_name {BVALID} -core_signal_name {axi4target_bvalid}

# Save the project after everything is done."
save_project
