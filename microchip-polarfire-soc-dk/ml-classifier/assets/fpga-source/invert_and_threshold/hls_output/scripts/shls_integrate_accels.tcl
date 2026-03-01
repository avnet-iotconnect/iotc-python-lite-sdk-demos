puts "TCL_BEGIN: [info script]"
open_smartdesign -sd_name {FIC_0_PERIPHERALS}

# Make script re-runnable: remove previous integration instances/component.
catch {sd_delete_instances -sd_name {FIC_0_PERIPHERALS} -instance_names {"tinyml_accel_top_0"}}
catch {sd_delete_instances -sd_name {FIC_0_PERIPHERALS} -instance_names {"soc_cycle_counter_inst"}}
catch {sd_delete_instances -sd_name {FIC_0_PERIPHERALS} -instance_names {"HLS_AXI4Interconnect_0"}}
catch {delete_component -component_name {HLS_AXI4Interconnect}}

puts "Creating HLS HDL+ cores"

set where [file dirname [info script]]
source [file join $where libero/create_hdl_plus.tcl]

puts "Creating HLS AXI interconnect"

create_and_configure_core -component_name {HLS_AXI4Interconnect} -core_vlnv {Actel:DirectCore:COREAXI4INTERCONNECT:2.8.103} -download_core -params {\
  NUM_SLAVES:2  NUM_MASTERS:1  NUM_MASTERS_WIDTH:1\
  ADDR_WIDTH:38 ID_WIDTH:8 CROSSBAR_MODE:1 NUM_THREADS:4 OPEN_TRANS_MAX:8 OPTIMIZATION:1\
DATA_WIDTH:64 MASTER0_DATA_WIDTH:64\
  SLAVE0_START_ADDR:0x70001000  SLAVE0_END_ADDR:0x70001007 SLAVE0_DATA_WIDTH:64 SLAVE0_TYPE:1\
  MASTER0_READ_SLAVE0:true MASTER0_WRITE_SLAVE0:true\
  SLAVE1_START_ADDR:0x70000000 SLAVE1_DATA_WIDTH:64 SLAVE1_TYPE:0 SLAVE1_END_ADDR:0x7000027f\
  MASTER0_READ_SLAVE1:true MASTER0_WRITE_SLAVE1:true\
}
sd_instantiate_component -sd_name {FIC_0_PERIPHERALS} -component_name {HLS_AXI4Interconnect} -instance_name {HLS_AXI4Interconnect_0}
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {HLS_AXI4Interconnect_0:ACLK ACLK}
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {HLS_AXI4Interconnect_0:ARESETN ARESETN}
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {AXI2AXI_TO_HLS:AXI4_MASTER HLS_AXI4Interconnect_0:AXI4mmaster0}

puts "Adding counter for profiling"

sd_instantiate_hdl_core -sd_name {FIC_0_PERIPHERALS} -hdl_core_name {invert_and_threshold_soc_cycle_counter} -instance_name {soc_cycle_counter_inst}

puts "Adding and connecting the accelerators into the smartdesign"

sd_instantiate_hdl_core -sd_name {FIC_0_PERIPHERALS} -hdl_core_name {tinyml_accel_top} -instance_name {tinyml_accel_top_0}

puts "Making connections"
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {soc_cycle_counter_inst:axi4target HLS_AXI4Interconnect_0:AXI4mslave0}
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {soc_cycle_counter_inst:i_reset ARESETN}
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {soc_cycle_counter_inst:i_clk ACLK}
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {tinyml_accel_top_0:axi4target HLS_AXI4Interconnect_0:AXI4mslave1}
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {tinyml_accel_top_0:reset ARESETN}
sd_connect_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {tinyml_accel_top_0:clk ACLK}
sd_invert_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {soc_cycle_counter_inst:i_reset}
sd_invert_pins -sd_name {FIC_0_PERIPHERALS} -pin_names {tinyml_accel_top_0:reset}
# Call hls_user_connections, if defined. The user can create additional
# connections manually
if {[llength [info procs hls_user_connections]]} {
    hls_user_connections
}
generate_component -component_name {FIC_0_PERIPHERALS} -recursive 0
build_design_hierarchy
save_smartdesign -sd_name {FIC_0_PERIPHERALS}
puts "TCL_END: [info script]"
