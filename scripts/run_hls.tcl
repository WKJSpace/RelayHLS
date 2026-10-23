# Explicit user-invoked reproduction. Requires Vitis HLS 2025.2.
# Example: RELAYHLS_WORKLOAD=bb72 RELAYHLS_POINT=c4v8 RELAYHLS_STAGE=synthesis
#          vitis-run --mode hls --tcl scripts/run_hls.tcl
set repo [file normalize [file join [file dirname [info script]] ..]]
foreach key {RELAYHLS_WORKLOAD RELAYHLS_POINT RELAYHLS_STAGE} {
    if {![info exists ::env($key)]} { error "Set $key" }
}
set workload $::env(RELAYHLS_WORKLOAD)
set point $::env(RELAYHLS_POINT)
set stage $::env(RELAYHLS_STAGE)
if {$workload ni {bb72 bb144} || $point ni {c1v2 c1v4 c1v8 c2v2 c2v4 c2v8 c4v2 c4v4 c4v8}} {error "Unsupported selection"}
if {$workload eq "bb144" && $point ne "c4v8"} {error "BB144 includes only C4V8"}
if {$stage ni {csim synthesis cosim}} {error "Stage must be csim, synthesis or cosim"}
set fixture [file join $repo benchmarks $workload $point]
set build [file join $repo build ${workload}-${point}-${stage}]
if {[file exists $build]} {error "Build directory exists; choose a fresh checkout for a new attempt"}
file mkdir $build
cd $build
open_component [file join $build circuit_full_top] -flow_target vivado
set_top relaybp_top
add_files [file join $fixture src decoder_top.cpp]
set input [file join $fixture inputs.txt]
set flags "-I\"[file join $fixture src]\" -DRELAYHLS_INPUT_PATH=\"\\\"$input\\\"\""
add_files -tb [file join $fixture testbench full_top.cpp] -cflags $flags
set_part {xcvu9p-flga2104-2L-e}
create_clock -period 10 -name default
csim_design
if {$stage in {synthesis cosim}} {csynth_design}
if {$stage eq "cosim"} {cosim_design -rtl verilog -tool xsim -trace_level all}
exit
