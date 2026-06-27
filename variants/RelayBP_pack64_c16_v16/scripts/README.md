# scripts

Variant-local automation.

- `run_hls_ooc_10ns.sh`: runs Vitis HLS C synthesis using `hls_config.cfg`, then runs a direct Vivado out-of-context implementation of `relaybp_top` at 10 ns.

The script is portable inside this repository and does not depend on the original qLDPC workspace path.
