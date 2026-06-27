#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bad=0
for variant in RelayBP_pack64_c8_v16 RelayBP_pack64_c16_v16 RelayBP_pack64_c16_v32; do
  dir="$ROOT/variants/$variant"
  echo "[$variant] checking config"
  grep -qx 'syn.top=relaybp_top' "$dir/hls_config.cfg" || { echo "missing syn.top"; bad=1; }
  grep -qx 'tb.file=./testbench/relaybp_tb.cpp' "$dir/hls_config.cfg" || { echo "missing tb.file"; bad=1; }
  python3 -m json.tool "$dir/vitis-comp.json" >/dev/null
  grep -q 'hls_config.cfg' "$dir/vitis-comp.json" || { echo "vitis-comp does not link hls_config.cfg"; bad=1; }
done
exit "$bad"
