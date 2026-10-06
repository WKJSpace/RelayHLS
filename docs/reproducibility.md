# ARC Source Reproducibility

## Configuration and control

Each `variants/RelayBP_pack64_*` directory contains its source, graph tables,
JSON generator configuration, scalar testbench and Vitis component settings.
The C8 and C16 fixtures have equal dimensions but different graph topologies.
They are synthetic architecture workloads, with zero logical-action and commit
mask placeholders. They are not physical temporal-decoding benchmarks.

The corrected controller starts with one message-initialization pass. It tries
four sequential strengths, with at most ten updates per leg and forty total.
Only `(leg == 0 && local_update == 0)` bypasses posterior mixing. Later legs
carry state forward. Syndrome checks run every two updates and at a leg's final
update. Only converged candidates enter prior-weighted cost selection; the first
strict minimum wins ties, and two candidates end the default search.

This is an early-terminating controller. A projected forty-update stage sum is
not its measured execution time. Software or hardware comparisons must use the
same arithmetic, initialization, checks, cost selection and output boundaries.

## Source validation

```bash
./scripts/check_project.sh
./scripts/run_unit_tests.sh
python3 scripts/run_native_tests.py --include /path/to/Vitis/include
./scripts/run_csim_all.sh
```

The shared native regression uses the independent edge-index scalar reference
in each testbench. It compares controller correction, update/candidate counts,
convergence and all five public top outputs. Each input is reused to check that
consecutive calls do not retain old decoder state. Separate checks exercise all
four leg starts and exhaustive fixed-point bias values. Native compilation needs
Vitis arbitrary-precision headers and GMP; `--gmp` accepts a full runtime-library
path when `-lgmp` is unavailable.

Generator tests cover bank conflicts and edge coverage. The shared ARC contract
also compares every synthetic array with the committed header and checks that
both generators preserve the packed-prior interface and omit unused tables.

## Hardware flow and results

After C simulation passes, run `./scripts/run_hls_ooc_all.sh` to request synthesis
and OOC implementation. Reports are generated locally and excluded from Git.
An `II=1` directive is a synthesis request; inspect the achieved loop interval
and warnings before making a throughput claim.

ARC experiments are ongoing. No quality, latency, resource, power or energy
results are published in this source update. Earlier CSVs belong to historical
code and remain available in Git history. A source regression or completed HLS
run does not establish RTL agreement, physical latency or board energy.
