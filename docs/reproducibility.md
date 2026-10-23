# Reproduction

## Offline evidence checks

Python 3.10 or newer is sufficient. These commands start no compiler, decoder,
vendor tool or network request:

```bash
python3 scripts/verify_release.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

`SHA256SUMS` covers released files. `release_manifest.json` separately records
original and public source/fixture hashes. Checks cover fixture dimensions,
ordered cases, complete-group schedules, evidence/result bindings, timing and
energy calculations, workbook selection, and resource percentage formatting.

## Native reproduction

Use a C++17 compiler, GMP and installed AMD arbitrary-precision headers:

```bash
python3 scripts/run_native.py bb72 c4v8 --include /path/to/Vitis/include
python3 scripts/run_native.py bb144 c4v8 --include /path/to/Vitis/include
```

`--gmp /path/to/libgmp.so` selects an explicit library when necessary.
Each invocation refuses an existing output directory. Compilation is limited
to 900 seconds and the 32-case test to 600 seconds. The runner compares every
output byte with the frozen golden file. This functional test is not a timing
benchmark.

## Vitis HLS and ordinary RTL co-simulation

Saved hardware results used Vitis/Vivado 2025.2 (2025.2.1 installation) and
VCU118 `xcvu9p-flga2104-2L-e`. Other versions may schedule differently. Install
AMD tools, headers and licenses separately.

Choose `csim`, `synthesis`, or `cosim` explicitly:

```bash
RELAYHLS_WORKLOAD=bb72 RELAYHLS_POINT=c4v8 RELAYHLS_STAGE=csim \
  vitis-run --mode hls --tcl scripts/run_hls.tcl

RELAYHLS_WORKLOAD=bb144 RELAYHLS_POINT=c4v8 RELAYHLS_STAGE=cosim \
  vitis-run --mode hls --tcl scripts/run_hls.tcl
```

The portable Tcl creates a fresh component. `cosim` runs the ordinary vendor
C/RTL flow, including C simulation and synthesis. Compare the 32 numeric
C-simulation result lines with `golden.txt`. A vendor Pass alone is insufficient:
verify all five C/RTL output traces over 32 cases, and extract 32 latencies and
31 service intervals from the generated transaction report. Both full-group
loops, `CNU_ROW_GROUPS` and `VNU_GROUPS`, must achieve II=1 with the expected
detector/CN-lane and stored-fault/VN-lane trip counts.

The portable entry points are statically reviewed release recipes. They were
not used to rerun closed experiments during packaging. Saved results belong
to the pinned original source/testbench/tool bindings; the portable testbench
differs only in its fixture-path expression.

## Routing completed frozen RTL

After genuine co-simulation and output/preservation checks pass, copy the
complete accepted Verilog tree and referenced initialization files into a fresh
`route/rtl/`, preserving relative references. Copy `scripts/route_full_top.tcl`
and `scripts/constraints.xdc` to `route/`. Record the complete frozen tree hashes.

```bash
cd route
vivado -mode batch -source route_full_top.tcl
```

The routing Tcl is byte-identical to the validated helper. It produces seven
reports and a routed checkpoint. Confirm full routing, nonnegative setup/hold/
pulse slack, no internal unconstrained paths, device fit and preservation of
source/constraints/frozen RTL/readmem files. OOC I/O boundaries do not establish
a board I/O contract.

The original campaigns used 24-hour HLS and ordinary RTL limits and a 6-hour
route limit. These public recipes do not include laboratory process supervision.
Preserve failures and reports. File growth or silence does not establish success.

## New configurations

`config.json` records the generated snapshot; synthesis does not read it.
Use a fresh directory, regenerate all graph and memory-access tables together,
and establish fresh scalar/native, C-simulation, complete-group II, ordinary RTL
and routing evidence. Results do not transfer automatically to a different code,
lane/bank count, precision, tool version or fixture. Frozen validated constants
are included; a general automatic circuit-to-bitstream generator is not.
