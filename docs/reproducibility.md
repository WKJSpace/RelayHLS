# Evaluation Reproducibility

The committed variants correspond to the three RelayHLS parallelism points
reported in the accompanying paper. This document fixes the workload and
measurement boundaries so independently collected reports can be compared
without conflating a BP update, a checked workload, and host communication.

## Common Benchmark

- Detector-fault graph: 1,008 detector rows, 9,000 candidate-fault columns,
  7,349 active columns, and 8,064 edges.
- CN degree: eight for every detector row.
- Maximum VN degree: eight.
- Message format: four-bit magnitude plus sign; posterior storage adds three
  guard bits.
- Banking: 64 banks for edge, prior, posterior, and packed binary state.
- Clock target: 10 ns on `xcvu9p-flga2104-2L-e`.

The synthetic graph is deterministic. It is intended to isolate the
architecture-level effect of CNU/VNU scaling while retaining a large,
nontrivial sparse graph; it is not a circuit-level logical-error benchmark.

## Fixed-Work Normalization

The paper-normalized decoder workload consists of:

1. one message-initialization pass;
2. four leg slots with ten CN/VN updates each (40 BP updates total);
3. convergence checking every two updates (20 checks total); and
4. one prior-weighted candidate-cost pass.

Early termination is disabled for this comparison. The fixed decoder kernel
excludes commit-mask, detector-response, carry-extraction, output marshaling,
and PCIe/DMA transfer. These stages are reported separately.

The public controller retains its bounded runtime controls. The 40-update
paper value is obtained by composing measured stage cycles at the routed
100-MHz clock, rather than by treating the latency of one update as a complete
decode.

## Result Provenance

- `results/postroute_summary.csv` contains the routed timing, utilization,
  vectorless power estimate, and derived fixed-work metrics.
- `results/stage_cycles_c16_v32.csv` contains standalone HLS stage estimates
  used in the fixed-work cycle equation.
- `src/constants.h` contains the generated graph tables and compile-time
  settings for each variant.
- `configs/constants_config.json` records the human-reviewable generator
  parameters.

Power values are medium-confidence vectorless Vivado estimates. Energy is
therefore an estimate computed as routed total power multiplied by the
cycle-derived checked-kernel latency.

## Validation Order

```bash
./scripts/check_project.sh
./scripts/run_unit_tests.sh
./scripts/run_csim_all.sh
./scripts/run_hls_ooc_all.sh
```

The first two commands do not require Vitis. C simulation cross-checks the HLS
top against the scalar fixed-point reference contained in each testbench.
