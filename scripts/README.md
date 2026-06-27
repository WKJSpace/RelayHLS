# scripts

Repository-level automation for FlexRelay-HLS.

- `common.sh`: shared variant list and environment setup.
- `run_csim_all.sh`: runs C simulation for every variant using its `hls_config.cfg`.
- `run_hls_ooc_all.sh`: runs HLS synthesis and direct Vivado OOC implementation for every variant.
- `clean_generated.sh`: removes generated Vitis/Vivado artifacts.
- `check_project.sh`: validates basic project linkage and top/testbench settings.

All scripts should be run from the repository root unless noted otherwise.
