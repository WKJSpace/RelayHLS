#!/usr/bin/env bash
set -euo pipefail

load_vitis_env() {
  if command -v vivado-2025.2 >/dev/null 2>&1; then
    vivado-2025.2 >/tmp/relayhls_vivado_env.log 2>&1 || true
  fi
  export VITIS_BIN=${VITIS_BIN:-/home/cad/xilinx/Vivado-2025.2/2025.2/Vitis/bin}
  export VIVADO_BIN=${VIVADO_BIN:-/home/cad/xilinx/Vivado-2025.2/2025.2/Vivado/bin}
}

variants() {
  printf '%s\n' RelayBP_pack64_c8_v16 RelayBP_pack64_c16_v16 RelayBP_pack64_c16_v32
}
