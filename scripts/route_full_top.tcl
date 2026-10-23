# Independent non-project OOC build of frozen, completed HLS RTL.
# No board, PCIe/DMA, bitstream generation, programming or I/O deadline claim.
set task_root [file normalize [file dirname [info script]]]
set task_report_dir [file join $task_root reports]
file mkdir $task_report_dir
set_param general.maxThreads 16
cd [file join $task_root rtl]
read_verilog [lsort [glob *.v]]
read_xdc -mode out_of_context [file join $task_root constraints.xdc]
synth_design -top relaybp_top -part xcvu9p-flga2104-2L-e -mode out_of_context -flatten_hierarchy rebuilt
write_checkpoint -force [file join $task_root post_synth.dcp]
report_utilization -file [file join $task_report_dir post_synth_utilization.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $task_report_dir post_synth_timing.rpt]
opt_design
place_design
phys_opt_design
route_design
write_checkpoint -force [file join $task_root routed.dcp]
report_route_status -file [file join $task_report_dir route_status.rpt]
report_drc -file [file join $task_report_dir routed_drc.rpt]
report_utilization -file [file join $task_report_dir routed_utilization.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $task_report_dir routed_timing.rpt]
report_power -file [file join $task_report_dir routed_vectorless_power.rpt]
exit
