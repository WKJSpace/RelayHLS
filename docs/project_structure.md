# Project Structure

FlexRelay-HLS is organized around independent variants rather than a single mutable HLS project.
This prevents Vitis-generated state from one parallelism setting from leaking into another.

```text
FlexRelay-HLS/
  variants/
    RelayBP_pack64_c8_v16/
    RelayBP_pack64_c16_v16/
    RelayBP_pack64_c16_v32/
  scripts/
  docs/
  examples/
```

Each variant can be opened directly in Vitis because it contains `vitis-comp.json` and `hls_config.cfg`.
Generated folders are intentionally excluded from Git.
