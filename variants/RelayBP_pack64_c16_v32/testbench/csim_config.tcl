open_component relaybp_csim -reset -flow_target vivado
set_top relaybp_top
add_files ../src/decoder_top.cpp
add_files -tb relaybp_tb.cpp
set_part {xcvu9p-flga2104-2L-e}
csim_design
exit
