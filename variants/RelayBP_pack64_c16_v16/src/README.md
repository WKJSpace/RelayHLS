# src

Synthesizable Vitis HLS source for the Relay-BP qLDPC decoder.

Important files:

- `decoder_top.cpp` / `decoder_top.h`: external HLS interface and `relaybp_top` entry point.
- `relay_bp.h`: high-level Relay-BP decode flow.
- `bp_iteration.h`: CNU/VNU iteration orchestration.
- `cnu.h` and `vnu.h`: check-node and variable-node update kernels.
- `packed_bits.h`, `types.h`, `tools.h`, `windowing.h`: packed data types, helper logic, and window/carry handling.
- `constants.h`: generated design constants and static parameter checks.

Do not edit generated structural tables in `constants.h` by hand unless you are intentionally bypassing the generator flow.
