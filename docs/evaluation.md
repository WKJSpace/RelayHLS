# Evaluation scope

The release includes nine validated BB72 configurations and only BB144
C4V8/b128, the configuration with the highest validated throughput. Other
BB144 points and unsuccessful scaling attempts are outside this selection.

Per-configuration saved evidence covers ordered 32-case native equivalence,
successful C simulation and HLS synthesis, top XML, and achieved II=1 for both
complete-group CN/VN loops. Genuine ordinary RTL co-simulation passed with
vendor exit zero, 32 cases, 160 public output-field comparisons, 32 latencies
and 31 start-to-start intervals. Source/configuration, frozen RTL and memory
initialization files were preserved.

Completed out-of-context routing uses a 10 ns clock and 0.1 ns uncertainty,
passing setup/hold/pulse checks, internal timing constraints and device fit.
Audits retain seven report hashes and a routed checkpoint hash. Generated
implementation products are not bundled.

For clock frequency `f` in Hz:

```
mean latency [s] = sum(32 latency cycles) / (32 * f)
service rate [decodings/s] = 31 * f / sum(31 service interval cycles)
```

The timing CSV retains every RTL case and service interval. HLS estimates are
separate from RTL timing and routed utilization. None are operating-board
performance measurements.

## Matched BB72 CPU/GPU comparison

CPU and GPU use the same 32 ordered BB72 inputs, arithmetic, controller policy
and five public outputs. Setup and checking are outside timing. CPU runs include
scalar, SIMD and several thread counts. GPU runs include resident-device and
host-transfer boundaries. Reciprocal mean CPU/GPU latency is labeled as such;
it is not an independently measured sustained service rate.

Energy measurements use separate matched windows. CPU energy sums two CPU
package counters on a shared AMD EPYC 9554 host, includes background package
activity and excludes DRAM/whole-server energy. NVIDIA L40S energy uses NVML
cumulative device counters on a shared host. Gross and incremental energy
are separate, with sample-boundary uncertainty where available.

FPGA energy uses Vivado **post-route vectorless on-chip power estimates** with
Medium reported confidence. Estimated energy per decoding is power divided
by RTL service rate. It excludes board, host and I/O energy. The 201.9× CPU and
23.5× resident-GPU efficiency ratios compare gross package/device measurements
with the FPGA estimate. They are not measured whole-system energy savings or
uncertainty bounds. No matched BB144 CPU/GPU comparison was performed.

These fixtures do not establish logical-error rates, streaming backlog behavior,
hardware I/O latency, or platform-specific real-time QEC deadlines.
