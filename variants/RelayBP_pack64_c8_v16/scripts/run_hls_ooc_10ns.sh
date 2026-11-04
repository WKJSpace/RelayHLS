#!/usr/bin/env bash
set -euo pipefail
VARIANT=RelayBP_pack64_c8_v16
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT/scripts/common.sh"
load_vitis_env

cd "$ROOT/variants/$VARIANT"
mkdir -p logs

if grep -q '^clock=' hls_config.cfg; then
  sed -i -E 's/^clock=.*/clock=10ns/' hls_config.cfg
else
  printf '\nclock=10ns\n' >> hls_config.cfg
fi
if grep -q '^package.output.syn=' hls_config.cfg; then
  sed -i -E 's/^package\.output\.syn=.*/package.output.syn=false/' hls_config.cfg
fi

"$VITIS_BIN/v++" -c --mode hls --config hls_config.cfg --work_dir . > logs/hls_compile.log 2>&1

top_v=hls/syn/verilog/relaybp_top.v
if [ ! -s "$top_v" ]; then
  echo "missing $top_v" >&2
  exit 2
fi

impl_dir="hls/impl/direct_vivado_${VARIANT}_10ns_impl_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$impl_dir"
cat > "$impl_dir/run_impl_only.tcl" <<'TCL'
create_project -force impl_only_project . -part xcvu9p-flga2104-2L-e
set_property target_language Verilog [current_project]
read_verilog [glob -nocomplain "../../syn/verilog/*.v"]
set fp [open clock.xdc w]
puts $fp {create_clock -name ap_clk -period 10.000 [get_ports ap_clk]}
close $fp
add_files -fileset constrs_1 clock.xdc
synth_design -mode out_of_context -top relaybp_top -part xcvu9p-flga2104-2L-e
report_utilization -file util_synth.rpt
report_timing_summary -file timing_synth.rpt
opt_design
place_design
phys_opt_design
route_design
report_route_status -file route_status.rpt
report_clock_utilization -file clock_utilization_routed.rpt
report_utilization -file util_routed.rpt
report_timing_summary -file timing_routed.rpt
report_timing -max_paths 20 -file timing_paths_routed.rpt
write_checkpoint -force routed.dcp
exit
TCL

(cd "$impl_dir" && "$VIVADO_BIN/vivado" -mode batch -source run_impl_only.tcl > vivado_impl.log 2>&1)
