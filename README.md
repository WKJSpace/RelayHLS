# RelayHLS: Reusable Node Lanes for Quantum LDPC Decoding on FPGAs

RelayHLS is a parameterized FPGA architecture for Relay belief propagation (Relay-BP). Reusable check-node and variable-node lanes, banked on-chip message memories, and graph-derived access schedules expose the trade-off between decoding latency and FPGA resources.

## Quick Start

The current implementation and evaluation artifact are available at **[RelayHLS review artifact](https://anonymous.4open.science/r/RelayHLS-F668/)**.

1. Open the artifact's README for representative results and usage instructions.
2. Download its ZIP to obtain the decoder source, generated constants, test fixtures, and validation data.
3. Follow Quick Start for native execution, or inspect the supplied evaluation workbook without FPGA tools.

The artifact includes the BB72 configuration sweep, the highest-throughput validated BB144 configuration, matched CPU/GPU comparisons for both workloads, and instructions for native execution, HLS, RTL co-simulation, and routing. Optional offline checks verify file integrity and the supplied result calculations.

## Architecture

- Reusable CN/VN lanes process complete node neighborhoods.
- Banked storage, static access tables, and fixed-destination gathers coordinate computation and memory bandwidth.
- Fixed-point arithmetic and multi-leg control support convergence checks, prior-weighted candidate selection, and correction-related outputs.

The current source and validation datasets are distributed through the linked review artifact. Earlier synthetic variants in this repository's history are superseded by that release.

## License

See [LICENSE](LICENSE) for the MIT terms. External toolchains and software dependencies retain their own licenses.
