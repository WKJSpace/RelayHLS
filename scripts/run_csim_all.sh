#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/common.sh"
load_vitis_env

for variant in $(variants); do
  echo "[$variant] C simulation start"
  (cd "$ROOT/variants/$variant" && "$VITIS_BIN/vitis-run" --mode hls --csim --config hls_config.cfg --work_dir .)
  echo "[$variant] C simulation done"
done
