#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/common.sh"
load_vitis_env

for variant in $(variants); do
  echo "[$variant] HLS + OOC implementation start"
  "$ROOT/variants/$variant/scripts/run_hls_ooc_10ns.sh"
  echo "[$variant] HLS + OOC implementation done"
done
