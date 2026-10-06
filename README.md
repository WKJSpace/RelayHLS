# RelayHLS

RelayHLS is a configurable Vitis HLS implementation of Relay belief
propagation (Relay-BP) for FPGA-based quantum LDPC decoding. It maps the
complete decoder flow to a shared, banked datapath: fixed-point message
initialization, check-node and variable-node updates, up-to-four sequential
DMem-BP legs, convergence checking, candidate selection, and correction-related
processing.

This is the corrected RelayHLS source revision. It includes the corrected multi-leg
controller and banked datapath. The three synthetic configurations
are reproducibility fixtures; their dimensions do not establish decoding quality
on a physical quantum circuit. Experimental results are withheld while the RelayHLS
campaigns are running.

## RelayHLS Controller

- Four leg strengths: `beta = {7, 5, 3, 1}/8`, `gamma = 1 - beta`.
- The prior-only bypass applies once, at the first update of the initial leg.
  Later legs retain the previous posterior and edge messages.
- Default budget: ten updates per leg, forty total; check every two updates.
- Converged candidates are scored by parallel prior-bank accumulation. The
  lowest-cost correction is retained; two candidates end the default search.
- The VNU traverses continuous groups. A private decode buffer is copied to
  the dataflow output after frame and carry processing is complete.

## Architecture at a Glance

- **Reusable CNU/VNU lanes:** `CNU_PARALLEL` and `VNU_PARALLEL` select the
  synthesis-time compute width.
- **Banked decoder state:** V2C, C2V, prior, posterior, syndrome, and
  correction memories remain on chip across Relay-BP legs.
- **Generated static mapping:** graph-specific tables assign each scheduled
  edge access to a lane, local slot, BRAM bank, and bank address while checking
  the dual-port constraint.
- **Fixed-point datapath:** message magnitude, posterior guard width, packing,
  and memory factors are compile-time parameters.
- **Complete control path:** the HLS top includes multi-leg execution,
  convergence checks, minimum-cost candidate retention, and correction-related
  outputs.

## Included Variants

| Variant | CNU lanes | VNU lanes | Check lanes | Purpose |
|---|---:|---:|---:|---|
| `RelayBP_pack64_c8_v16` | 8 | 16 | 8 | Resource-oriented point |
| `RelayBP_pack64_c16_v16` | 16 | 16 | 16 | CNU-scaling point |
| `RelayBP_pack64_c16_v32` | 16 | 32 | 16 | Wider VNU point |

All three variants use 64-bit packed binary interfaces, 64 message-memory
banks, four-bit message magnitudes, and deterministic synthetic benchmarks
with 1,008 detectors, 9,000 candidate-fault slots and 8,064 edges. The C8
variant has 7,961 active columns; both C16 variants have 7,349. These are
equal-size workloads; the C8 and C16 graph topologies differ. Each directory
is self-contained so its Vitis project and generated constants can be opened,
validated, and implemented independently.

## Requirements

- AMD Vitis HLS and Vivado 2025.2
- VCU118 target device `xcvu9p-flga2104-2L-e`
- Python 3.9 or newer for graph generators and unit tests
- Bash for repository-level automation

The scripts first look for the laboratory environment command
`vivado-2025.2`. On another system, set `VITIS_BIN` and `VIVADO_BIN` to the
corresponding installation directories.

## Quick Start

Run repository checks and generator unit tests without invoking Vitis:

```bash
./scripts/check_project.sh
./scripts/run_unit_tests.sh
```

Run C simulation for all three variants:

```bash
./scripts/run_csim_all.sh
```

Run HLS synthesis and direct Vivado out-of-context implementation:

```bash
./scripts/run_hls_ooc_all.sh
```

Run only the C16/V32 variant:

```bash
cd variants/RelayBP_pack64_c16_v32
./scripts/run_hls_ooc_10ns.sh
```

The HLS top function is `relaybp_top`. See
[`docs/hls_flow.md`](docs/hls_flow.md) for the generated reports and
[`docs/reproducibility.md`](docs/reproducibility.md) for the evaluation
boundaries used in the paper.

## Adapting a Graph

Each variant provides two generator entry points:

- `tools/generate_fake_h_constants.py` recreates the controlled synthetic
  benchmark and verifies schedule/bank feasibility.
- `tools/generate_real_circuit_constants.py` imports a detector-fault graph
  derived from a circuit model.

Keep the selected parameters in `configs/constants_config.json` and generate
new headers into a separate file using `--output`. The renderers use the same
prior packing and FIFO declarations as the
committed headers. Review a generated header before replacing a configured
fixture. See [constant generation](docs/graph_generation.md).
Run the generator tests and pass C simulation before synthesis. The
generators reject schedules that exceed the available true-dual-port BRAM
accesses.

## Verification and Experimental Status

Run the native scalar and carried-leg regressions with the installed Vitis headers:

```bash
python3 scripts/run_native_tests.py --include /path/to/Vitis/include
```

Use `--gmp /full/path/to/libgmp.so` when the system has the GMP runtime without
its development linker alias. The test covers all three variants, all four leg
starts, repeated full-top calls, candidate cost, inactive columns and fixed-point
bias arithmetic. The graph generators are also checked against the committed
arrays and packed-prior interface.

RelayHLS quality, RTL, routing and board campaigns remain separate experiments. This
source update publishes no performance or logical-error results. Historical CSVs
are available in earlier revisions and do not describe this controller. Generated
Vitis/Vivado products stay outside Git. See [reproducibility](docs/reproducibility.md).

## Citation

Citation metadata is provided in [`CITATION.cff`](CITATION.cff). If you use
RelayHLS, please cite the associated paper and this repository.

## License

RelayHLS is released under the [MIT License](LICENSE).
