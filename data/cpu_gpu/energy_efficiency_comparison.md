# BB72 FPGA / CPU / GPU energy efficiency comparison

All decoding implementations use the same 32 ordered BB72 inputs and fixed-point decoding settings. Energy uses repeated batch-one decoding, not a batch throughput kernel. **Measurement scopes differ:** CPU package and GPU device counters are measured; FPGA on-chip energy is modeled, not board-measured.

| Implementation | Active power (W) | Gross energy (mJ/decoding) | Decodings/J | Evidence / scope |
|---|---:|---:|---:|---|
| CPU / Supernova EPYC 9554 simd-1 | 235.522 | 212.129 | 4.714 | measured_package_counters; sum of 2 CPU packages on shared Supernova; includes background; excludes DRAM/whole-server |
| GPU / Bahama L40S / resident | 99.866 | 24.718 | 40.457 | measured_device_counters; whole GPU device, shared host; resident |
| GPU / Bahama L40S / host_transfer | 100.287 | 26.962 | 37.089 | measured_device_counters; whole GPU device, shared host; host_transfer |
| FPGA / RelayHLS C4V8 b128 | 4.741 | 1.051 | 951.820 | vectorless_model_estimate; estimated FPGA on-chip power divided by validated sustained RTL service rate |

## CPU calculation and validation

- Supernova EPYC 9554, SIMD, one decoding thread; 2 package domains sampled. The compiler and benchmark ran unprivileged; only the read-only energy sampler used sudo.
- Five active windows: 66,720 decodings over 60.092982645 s; integrated package energy 14153.222905887 J.
- Gross energy = total active-window joules / active-window decodings = **212.128641 mJ/decoding**.
- Efficiency = decodings / joules = **4.714121 decodings/J**; mean active package power = **235.522057 W**.
- Same-window throughput: 1110.279388 decodings/s; 900.674200 us/decoding is a sustained window average, distinct from per-call latency in CPU_GPU_latency.csv.
- Correctness: 11 full 32-input validation passes; 1,760 primary output-field comparisons; zero mismatches. Candidate selection counts were also checked by the pinned benchmark.
- 1,790 samples, max gap 0.100712472 s, max read span 0.000565689 s; every active and background window is bracketed. Zero counter wraps observed.
- Cumulative counters use the same CLOCK_MONOTONIC domain as benchmark windows. Piecewise-linear endpoint interpolation is used; no old latency is multiplied by separately observed power.
- Conservative monotonic-counter sampling-boundary range: **210.636019 to 214.162278 mJ/decoding**. Corresponding efficiency: 4.669356 to 4.747526 decodings/J. These bounds include read spans; they are not statistical confidence intervals and do not bound hardware-counter accuracy.
- Across five windows, sample standard deviation of gross energy: 0.273096 mJ/decoding. This is one shared-host experiment, not independent-run reproducibility.
- Counter-unwrapping admissibility assumes at most 2,000 W per package; counter ranges and sample gaps satisfy that conservative bound.

## Background adjustment: report separately

The CPU paired-background-adjusted point estimate is **3.347868 mJ/decoding**. Its conservative sampling-boundary range is **-7.939016 to 16.747964 mJ/decoding**, which includes zero. It must not be used as a precise decoding-only energy result or to rank CPU/GPU algorithm-only efficiency. Other activity on Supernova is not isolated by this subtraction.

GPU resident: paired-background-adjusted point estimate 4.365529 mJ/decoding. This remains a background adjustment, not isolated process energy.
GPU host_transfer: paired-background-adjusted point estimate 4.764128 mJ/decoding. This remains a background adjustment, not isolated process energy.

## Interpretation and provenance

- CPU gross values include both CPU packages and shared background activity; DRAM and wall-plug energy are excluded.
- GPU values include the GPU device, with resident and host-transfer modes shown separately. Host CPU/RAM and whole-server energy are excluded, including in host-transfer mode.
- FPGA values use post-route vectorless on-chip power (confidence Medium) divided by the validated 31-interval RTL service rate at routed 100 MHz. Switching activity is not matched to the 32-input trace; board power and wall-plug power are not measured.
- Accordingly, this is a same-workload comparison of explicitly labeled component scopes, not an apples-to-apples measured whole-platform energy claim.
- Original per-call CPU/GPU timing and energy-window rates remain separately labeled in the workbook. FPGA resource utilization uses VCU118 / XCVU9P capacities; utilization numbers are shown without a percent sign.
- This release workbook contains nine validated BB72 points and only BB144 C4V8. The BB72 energy comparison uses the independently validated C4V8, 128-bank result.
- CPU final receipt SHA256: `c2b9719f414bc7e402482a7cb7d5d68e310c00fc674bf5aa2f4aecdd419801b2`.
- CPU raw readings SHA256 (raw file retained on Supernova): `93e7e7bf0eeaef110ad31d86e979c163daf6701a1306fa1925bdaad0d15057ee`.
- CPU timing windows SHA256: `f51a53a29b1ca6e76c8473747032a5c115083dd52126ecb4a83b10d9f2a40c42`.
- CPU input SHA256: `12575d3aa73a6e6bd3e05198166fa6545dc02934238e5c49f9cff9127c8dacc0`.
- GPU final SHA256: `fdc05801f94f30e331bcf8e517c963836c4f1a8414ccf5e979edf60a545a379e`.
- FPGA routed final SHA256: `4957425c0ed6dee2697046ea42758fc4f20e780c45d6af07759506bfbee04e93`.

See CPU_energy_validation.json, CPU_energy_trials.csv, GPU_energy_trials.csv and ../bb72/validation/c4v8.json for filtered evidence and aggregate trial data.
