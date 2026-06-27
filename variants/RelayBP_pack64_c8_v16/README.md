# RelayBP_pack64_c8_v16

This directory is a self-contained Vitis HLS variant of FlexRelay-HLS.
It targets the qLDPC Relay-BP decoder with `PACK_BITS=64` and the parallelism encoded in the directory name.

## Contents

- `src/`: synthesizable C++ HLS source for `relaybp_top`.
- `testbench/`: deterministic C simulation testbench and Tcl helper.
- `tools/`: Python generators for fake-H and real-circuit-derived constants.
- `tests/`: Python tests for the constant generators.
- `configs/`: saved JSON settings used to regenerate `src/constants.h`.
- `scripts/`: local run helper for HLS synthesis and direct Vivado OOC implementation.
- `hls_config.cfg`: canonical Vitis HLS component configuration.
- `vitis-comp.json`: Vitis component file linked to `hls_config.cfg`.

## Top Function

The HLS top function is `relaybp_top`. The config must keep:

```ini
syn.top=relaybp_top
tb.file=./testbench/relaybp_tb.cpp
```

## Typical Flow

From this variant directory:

```bash
../../scripts/run_csim_all.sh
./scripts/run_hls_ooc_10ns.sh
```

Generated folders such as `hls/`, `logs/`, `.Xil/`, and `reports/` are intentionally ignored by Git.
