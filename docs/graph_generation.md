# Graph Constants and Their Consumers

This describes the public RelayHLS implementation based on commit
`3b8b7ffc943b19626f38cafa517949304a488067`. The cleanup removes unused
representations. All decoder files, interfaces, configurations, retained
constants and historical result files are preserved. Separately corrected
ARC experiment sources are maintained on Supernova and are not replaced
by this public artifact.

## 1. Disconnected candidate-fault columns

The committed graph is a synthetic sparse workload. `NUM_FAULTS = 9000`
sets the number of column/storage slots; it does not establish 9,000
physically derived fault mechanisms. Each of 1,008 detector rows has eight
edges, giving 8,064 edges. Some columns therefore have degree zero.

Counts obtained directly from the committed `H_COL_DEGREES` tables:

| Variant | Degree 0 | Degree 1 | Degree 2 | Degree 3 | Degree 4 | Active columns | Edges |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C8/V16 | 1,039 | 7,858 | 103 | 0 | 0 | 7,961 | 8,064 |
| C16/V16 | 1,651 | 6,667 | 650 | 31 | 1 | 7,349 | 8,064 |
| C16/V32 | 1,651 | 6,667 | 650 | 31 | 1 | 7,349 | 8,064 |

The following behavior already exists in the decoder:

- `init_messages` initializes all marginal slots from runtime priors. A
  degree-zero column has no valid edge entries and no associated messages.
- `vnu_pass` starts each packed decision word at zero and invokes the VNU
  only when `j < NUM_FAULTS && H_COL_DEGREES[j] > 0`. Inactive bits remain
  zero; their marginals are not updated by the VNU.
- `compute_weight` traverses `ACTIVE_FAULT_INDEX`, which contains only
  columns with positive degree. Inactive columns contribute no cost.
- The decoder clears the best estimate before decoding. Inactive columns
  therefore remain zero in its correction estimate.
- Prior/marginal capacity and the packed input/output dimensions still
  accommodate all 9,000 slots. The cleanup does not compact, renumber or
  resize the graph or its interfaces.

The C8 and C16 topologies differ because the greedy synthetic placement
uses parallel-group bank constraints. Matching dimensions and edge counts
do not imply identical graphs. This cleanup preserves both topologies.

A physical detector model can contain a fault with no detector edges but
nonzero logical action. Such a column is not automatically harmless.
This synthetic benchmark and its skip rule do not establish correct
decoding of logical-only faults; a physical-model evaluation must account
for that case explicitly.

## 2. Removed representations

The audited names have no references in the decoder or scalar testbench
outside their declarations. The cleanup removes their declarations from
the committed headers and their output from both renderers.

| Removed names | Meaning | Representation actually consumed |
| --- | --- | --- |
| `EDGE_BANK_FOR_CHECK_POS`, `EDGE_ADDR_FOR_CHECK_POS`, `EDGE_BANK_FOR_VAR_POS`, `EDGE_ADDR_FOR_VAR_POS` | Per-node slot to edge-memory bank/address | `CNU_EDGE_*` and `VNU_EDGE_*` schedules in the banked decoder |
| `H_COL_NEIGHBORS` | Check indices adjacent to each variable | `EDGE_FOR_VAR_POS` and degrees in the scalar reference; generated schedules in hardware |
| `H_CSR_ROW_PTR`, `H_CSR_COL_IDX` | CSR row pointers and column indices for H | Padded row tables in the scalar reference and detector schedules in hardware |
| `PRIOR_INIT` / `PRIOR_LAMBDA` | Unused dummy prior arrays | Packed prior input words; `PRIOR_INIT` was emitted by the renderers, while committed headers used `PRIOR_LAMBDA` |
| `A_CSR_ROW_PTR`, `A_CSR_COL_IDX` | CSR logical-action matrix | `A_ROW_DEGREES` and `A_ROW_NEIGHBORS` in `compute_a_times_e` |
| `CONVERGENCE_MASK` | Unused convergence-mask placeholder | `check_convergence` compares the full configured detector range |
| `CARRY_OUT_ROWS` | Unused carry-row lookup placeholder | `extract_carry` reads `CARRY_DETECTOR_START + m` |

The retained `H_ROW_NEIGHBORS`, `EDGE_FOR_CHECK_POS` and
`EDGE_FOR_VAR_POS` are used by the scalar testbench. `COMMIT_MASK`,
`A_ROW_DEGREES` and `A_ROW_NEIGHBORS` are used by window/output functions.
Their existing synthetic placeholder values are preserved.

External programs directly using a removed reference-array name will need
to use a retained representation or the baseline revision. The repository's
decoder and testbench do not use those names.

## 3. How the numbers are derived

Let H have detector rows i and fault columns j, with H[i,j] = 1 for an
edge. All indices below are zero based.

### Graph sizes, degrees and adjacency

- `NUM_DETECTORS = WINDOW_W * M_PER_CYCLE`.
- For the synthetic graph, `NUM_EDGES = NUM_DETECTORS * ROW_DEGREE`.
  For an imported graph, the edge count is the number of input nonzeros.
- `H_ROW_DEGREES[i] = sum_j H[i,j]` and
  `H_COL_DEGREES[j] = sum_i H[i,j]`.
- Synthetic edges receive consecutive IDs in detector-row/slot order:
  `e = i * ROW_DEGREE + slot`.
- `EDGE_FOR_CHECK_POS[i][slot]` and `EDGE_FOR_VAR_POS[j][slot]`
  hold those edge IDs in row/column adjacency order.
- `H_ROW_NEIGHBORS[i][slot]` contains the edge's fault index.
- `ACTIVE_FAULT_INDEX` is the sorted list of j with positive column degree.
- Padded adjacency slots contain zero. Degree values or schedule valid bits
  distinguish padding from a real edge/index zero.

The synthetic generator starts its search for a fault column at

```text
j0 = (1543 * e + 17 * i + 9973 * slot) mod NUM_FAULTS
```

It scans successive columns modulo `NUM_FAULTS` until it finds a column
below `H_MAX_COL_DEGREE`, absent from the current row, with feasible message
and detector-bank accesses. This is a deterministic synthetic construction,
not a model derived from a quantum circuit. The real-graph importer instead
uses the supplied detector/fault incidences and sorts faults within each row;
it rejects infeasible schedules without redirecting an edge to another fault.

### Edge-message banks

Define B = `EDGE_BANK_FACTOR`, PC = `CNU_PARALLEL`, and PV =
`VNU_PARALLEL`. The preferred bank for row i and slot s is

```text
b_preferred = ((i mod PC) + (s mod 4) * PC) mod B
```

Candidate banks are sorted by the pair

```text
(number_of_edges_already_in_bank[b], (b - b_preferred) mod B)
```

The first feasible bank is selected. It must have remaining address space
and fewer than two accesses in both its CNU group `floor(i / PC)` and VNU
group `floor(j / PV)`. The address is the number of earlier edges assigned
to the selected bank; the counter is then incremented.

```text
EDGE_BANK_DEPTH = ceil(NUM_EDGES / B)
```

Bank/address assignments thus depend on placement history and constraints;
they cannot be reproduced by simply applying `edge_id mod B`.

### CNU, VNU and detector schedules

For a node index x processed P at a time, `group = floor(x/P)` and
`lane = x mod P`. The slot is its position in that node's adjacency list.

`CNU_EDGE_*[group][bank][port]` and `VNU_EDGE_*[group][bank][port]`
store a valid bit, lane, adjacency slot and edge-memory address. Each bank
has two port entries; missing entries are invalid and contain zero fields.
All edges appear once in each respective schedule.

The detector schedule reads fault hard decisions. Its bank and address are

```text
bank(j) = j mod PACKED_BANK_FACTOR
address(j) = floor(j / PACKED_BANK_FACTOR)
```

It groups rows using `CONVERGENCE_PARALLEL` and stores valid, detector lane
and fault address in `DET_EDGE_*`. At most two edges per packed bank may
be scheduled in each group. Both syndrome checking and H-times-correction
use the retained detector schedule.

Prior storage uses the analogous mapping with `PRIOR_BANK_FACTOR`.
The committed prior ABI packs `MSG_INT_BITS` bits per prior into
`PRIOR_PACK_FACTOR * MSG_INT_BITS`-bit words.

### Logical action, commit and carry

For an imported logical-action matrix A, `A_ROW_DEGREES[k]` is its row
degree and `A_ROW_NEIGHBORS[k]` lists the sorted fault indices for that
observable. `compute_a_times_e` XORs the selected correction bits.
The committed synthetic A tables and commit mask are zero placeholders.
`extract_carry` reads the configured contiguous rows beginning at
`COMMIT_C * M_PER_CYCLE`. The cleanup preserves all of these values and
operations.

## Existing regeneration differences

The current renderers already emit `FIFO_DEPTH = WINDOW_W + 2` and
`PRIOR_WORD_BITS = 6 * PRIOR_PACK_FACTOR`, omit `NUM_PRIOR_WORDS`, and emit
extra `CNU_LANE_EDGE_*` / `VNU_LANE_EDGE_*` arrays. Committed headers use
`FIFO_DEPTH = WINDOW_W + COMMIT_C`, the message-width prior ABI and
`NUM_PRIOR_WORDS`, and do not contain those lane arrays.

The cleanup intentionally preserves each version's existing retained
declarations. Its tests lock separate signatures for committed headers
and synthetic renderer output. This is not a repair of the existing
regeneration differences: generate into a separate `--output` path and
review the ABI and configuration before replacing a committed header.

## Verification boundary

The cleanup is checked against the public baseline on Supernova with
retained-declaration comparisons, protected-file hashes, original generator
tests, cleanup contracts, native C++ testbenches and deterministic traces.
Compiled native decoder equality strengthens the behavior-preservation
check. It does not constitute new HLS synthesis, routed timing or physical
VCU118 measurement. Existing ARC experiment sources and running jobs use
their existing frozen files.

### Completed cleanup checks (2026-10-06)

- All three variants retain 84 constant declarations byte for byte.
  Header content outside the removed declarations is token-identical after
  ignoring comments and whitespace. There are no header additions.
- 53 protected implementation/configuration/result files match their baseline
  hashes. Non-rendering generator code has identical Python ASTs.
- All 81 generator and cleanup tests pass (27 per variant). The cleanup
  absence checks first failed against the unchanged baseline, while its
  retained-constant signature checks passed.
- Each original native C++ testbench passes before and after cleanup.
- Across 32 cases per variant, all 96 paired traces are identical. Each
  trace includes four BP updates with all scheduled edge messages,
  marginals, hard decisions, cost and convergence results, followed by the
  controller and top-level outputs. Inactive hard-decision bits remain zero.
- Optimized native decoder objects, testbench executables and trace
  executables are byte-identical for every variant.
- The two inspected corrected ARC controllers retain their prior hashes.
  Verification writes are confined to a separate cleanup directory.
- Twelve unused declarations are removed from each committed header,
  saving 1,022,856 bytes per variant (3,068,568 bytes total).

These checks preserve the public implementation's existing behavior,
including its historical settings. They do not promote the public artifact
to the separately corrected ARC version or establish new routed measurements.
