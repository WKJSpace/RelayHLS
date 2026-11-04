# variants

This folder contains independent HLS design variants.

Each variant has its own:

- HLS source and generated constants.
- Vitis component metadata.
- Testbench and generator tests.
- Reproducibility config in `configs/`.
- Local run script in `scripts/`.

Keep variants independent so synthesis reports and implementation results can be compared without cross-project state contamination.
