# Parameter Constraints

The design relies on compile-time constants generated into `src/constants.h`.
The generators and static checks should keep the following constraints valid:

- `PACK_BITS` must match the packed word layout used by the testbench and top interface.
- `CNU_PARALLEL` controls check-node row-group parallelism.
- `VNU_PARALLEL` controls variable-node lane-group parallelism.
- Banking must provide enough independent memory access ports for the chosen CNU/VNU schedule.
- Detector/fault dimensions must match the generated parity structure and packed input/output widths.
- `relaybp_top` is the only supported HLS top function for these variants.

When adapting a real quantum-circuit simulator result, regenerate constants through `tools/generate_real_circuit_constants.py`, save the generator configuration in `configs/`, then run generator tests and C simulation before synthesis.
