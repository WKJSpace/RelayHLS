# Variant Notes

Base project: `RelayBP_pack64_c16_v32`

This independent project variant uses `CNU_PARALLEL=8`, `VNU_PARALLEL=16`, and `CONVERGENCE_PARALLEL=8`.

Generated sparse H schedules are owned by this project in `src/constants.h` and should be regenerated with this project generator at `tools/generate_fake_h_constants.py`.
