# RelayHLS

RelayHLS is a Vitis HLS project for FPGA-oriented Relay-BP decoding of qLDPC codes.
The repository packages three independent `PACK_BITS=64` design variants used to study CNU/VNU parallelism and implementation scalability.

## Included Variants

- `RelayBP_pack64_c8_v16`: lower CNU/VNU parallelism reference.
- `RelayBP_pack64_c16_v16`: increased CNU parallelism with the same VNU parallelism.
- `RelayBP_pack64_c16_v32`: baseline/high-throughput configuration.

Each variant is intentionally self-contained under `variants/` and has its own `src/`, `testbench/`, tools, tests, Vitis component file, and HLS config.

## Requirements

- AMD/Xilinx Vitis and Vivado 2025.2 available on the build machine.
- Device target: `xcvu9p-flga2104-2L-e`.
- Python 3 for generator tools and tests.

The scripts assume the lab environment command `vivado-2025.2` is available. If not, set `VITIS_BIN` and `VIVADO_BIN` before running scripts.

## Quick Start

Validate C simulation for all variants:

```bash
./scripts/run_csim_all.sh
```

Run HLS C synthesis plus direct Vivado OOC implementation for all variants:

```bash
./scripts/run_hls_ooc_all.sh
```

Run one variant only:

```bash
cd variants/RelayBP_pack64_c16_v32
./scripts/run_hls_ooc_10ns.sh
```

## Vitis GUI

Open any variant directory as a Vitis HLS component. The component file is `vitis-comp.json`, and it links to the canonical config:

```json
"configFiles": ["hls_config.cfg"]
```

The top function is always:

```ini
syn.top=relaybp_top
```

## Repository Policy

Generated Vitis/Vivado outputs are not tracked. This includes `hls/`, `.Xil/`, `logs/`, `reports/`, `backups/`, `*.rpt`, and `*.log`.
Use `./scripts/clean_generated.sh` before committing if needed.
