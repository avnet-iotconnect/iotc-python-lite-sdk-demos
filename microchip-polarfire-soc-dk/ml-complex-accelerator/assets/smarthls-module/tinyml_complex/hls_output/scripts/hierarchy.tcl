add wave -hex -group "tinyml_accel_hw_top" -group "ports"  {*}[lsort [find nets -ports [lindex [find instances -bydu tinyml_accel_hw_top] 0]/*]]
add wave -hex -group "tinyml_accel_hw_top" -group "tinyml_accel" -group "ports"  {*}[lsort [find nets -ports [lindex [find instances -r /tinyml_accel_inst] 0]/*]]
