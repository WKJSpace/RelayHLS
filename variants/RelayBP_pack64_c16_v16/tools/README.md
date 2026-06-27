# tools

Python utilities for regenerating HLS constants.

- `generate_fake_h_constants.py`: creates synthetic qLDPC/Gross-code-style constants for design exploration.
- `generate_real_circuit_constants.py`: converts real circuit or detector-model data into project-compatible constants.

Use `--help` on each script to see supported input formats and parameter restrictions. Keep generated settings in `configs/constants_config.json` when a variant should be reproducible.
