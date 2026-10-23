# Validation data

Selection: all nine BB72 C1/C2/C4 × V2/V4/V8 points and **only BB144 C4V8**.
The workbook, source snapshots and JSON/CSV tables use the same selection.

| File or directory | Contents |
|---|---|
| `RelayHLS_Evaluation.xlsx` | Evaluation workbook; BB144 has C4V8 only |
| `evaluation.json` | Selected results, CPU/GPU measurements, capacities and limitations |
| `bb72/matrix.csv` | Nine validated BB72 points |
| `bb72/resource_utilization.csv` | Routed resource counts and numeric percentages |
| `bb144/matrix.csv`, `bb144/evaluation.json` | Best validated BB144 throughput point |
| `bb72/validation/`, `bb144/validation/` | HLS/RTL/route aggregate evidence and content hashes |
| `HLS_schedules.csv` | Complete-group II, trip counts, depths and HLS estimates for all ten points |
| `RTL_per_case_timing.csv` | 32 latency samples and 31 service intervals per point; cycles at 100 MHz |
| `cpu_gpu/CPU_GPU_latency.csv` | Matched BB72 timing summaries and boundaries |
| `cpu_gpu/CPU_GPU_per_input_latency.csv` | Per-input means across repeated timing trials |
| `cpu_gpu/CPU_energy_trials.csv`, `GPU_energy_trials.csv` | Measured energy windows, gross and incremental quantities |
| `cpu_gpu/energy_efficiency_comparison.*` | Component-scoped energy comparison |
| `cpu_gpu/CPU_energy_validation.json` | CPU counter/sample-boundary validation evidence |
| `cpu_gpu/timing_trials.json` | Retained matched timing campaign samples |

Case indices are zero-based and preserve input order. The final case has no
following service interval and has a blank service cell. Latency is per
transaction; service rate uses successive transaction starts.

Resource percentages are numeric **0–100**. Percent symbols appear only in
CSV/workbook headers. BRAM uses 18 Kb equivalents. JSON uses `_pct` or `_percent`
field names. Missing primitive breakdowns are null/blank, not zero use.

HLS estimates are separate from routed physical fit. FPGA `_est` energy/power
fields are vectorless on-chip estimates. CPU package and GPU device energy are
measured separately and do not represent whole-system energy. See
[`docs/evaluation.md`](../docs/evaluation.md) for boundaries and calculations.

Hashes identify original source, fixtures, HLS XML, RTL traces, completion
contracts, reports and checkpoints. Raw server logs and implementation products
are not bundled. Root `SHA256SUMS` checks the public files themselves.
