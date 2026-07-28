# RelayHLS Evaluation Data

This directory contains compact, machine-readable data underlying the
architecture-level evaluation. The terminology follows
[`docs/reproducibility.md`](../docs/reproducibility.md):

- **BP update:** one CNU pass followed by one VNU pass.
- **fixed core:** initialization, 40 BP updates, and one candidate-cost pass.
- **checked workload:** the fixed core plus 20 syndrome checks.
- **workload rate:** reciprocal of the checked-workload latency.

Generated HLS/Vivado report directories are not committed. Regenerate them
with `scripts/run_hls_ooc_all.sh`.
