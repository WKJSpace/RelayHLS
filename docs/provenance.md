# Source and data provenance

`release_manifest.json` lists exact validated and public file hashes for ten
hardware snapshots: nine BB72 configurations and BB144 C4V8/b128 only. All
synthesizable C++/headers, generated graph/bank tables, configuration records,
ordered inputs and golden output bytes match the accepted snapshots.

Only `testbench/full_top.cpp` changes: its absolute input filename is replaced
by `RELAYHLS_INPUT_PATH`, defaulting to `inputs.txt`. The portable Tcl supplies
the local checkout path. Both hashes and this edit are recorded. No decoding
arithmetic, graph, schedule, controller or expected result is edited for release.

Native/HLS/top-XML/RTL/route bindings and report hashes are retained in each
aggregate validation record. Numeric per-case RTL timing records retain the
accepted trace hash. Packaging verified these saved sources and evidence
without repeating an accepted experiment.

`benchmarks/software/` retains the five hash-pinned BB72 CPU/GPU timing sources:
CPU full-top harness, scalar/SIMD/OpenMP baseline, model exporter, GPU timing
harness and fused kernels. The timing campaign's HLS-C reference used an earlier
graph-equivalent hardware source layout. `source_provenance.json` records its
original pins; the hardware snapshots released here are the later validated
gather implementations. Recompiling the software harness against a new header
layout does not reproduce an identical timing binary. GPU reproduction also
needs a numerical `model.json` exported from the matched graph and a hash-bound
`data-contract.json`. The frozen timing and energy results are supplied without
rerunning those experiments.

Full server logs, process details, binaries, licensed tools, raw simulation
traces and generated implementation products remain outside the repository.
A routed DCP hash is provenance, not a distributed checkpoint or board
measurement. Source and released validation data follow the MIT license.
External AMD, GMP, NumPy, PyTorch and Triton installations retain their own
licenses. Citation metadata does not invent a paper DOI or archival accession.
