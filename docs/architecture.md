# Architecture and interface

RelayHLS time-multiplexes CN and VN processing lanes across graph nodes.
Each scheduled group contains complete neighborhoods. CN and VN passes execute
in sequence; lanes operate in parallel within a pass. Generated maps select
bank addresses and fixed lane slots for bank-to-lane gathers and lane-to-bank
scatters. Lane-local CN reduction trees compute the check updates.

The top function is `relaybp_top`. It consumes packed syndrome bits, packed
fault-prior magnitudes, and carry input. It produces a packed fault estimate,
logical-frame update, carry output, iteration count, and convergence flag.
The golden text additionally records the controller's candidate count.
Prior values are supplied in the fixture, rather than inferred from syndrome
bits. The figure separates these input roles.

Messages and posterior state carry across Relay-BP legs. The four strengths are
`beta = {7,5,3,1}/8`; the prior-only bypass applies at the first update of the
first leg. Each leg permits ten updates, with a 40-update global limit and
convergence checks every two updates. Up to two converged candidates are scored
by prior-weighted cost.

| Fixture | Detectors | Stored fault slots | Edges | Logical observables |
|---|---:|---:|---:|---:|
| BB72 Z | 252 | 2,240 | 7,776 | 12 |
| BB144 Z | 936 | 8,832 | 30,672 | 12 |

The BB144 graph has 8,784 active fault slots. Both released testbenches use a
whole-memory, zero-carry fixture with mapped faults committed together.
The interface supports carry-related processing, but this fixture is not an
overlapping physical-streaming validation. `WINDOW_W=2` describes the generated
storage/interface geometry and does not by itself establish the number of
physical QEC rounds represented by a circuit-derived graph.

For a different graph, regenerate all dependent graph constants, edge-bank
assignments, group schedules and CN/VN reverse lookup tables together. Generate
syndromes from the new matrix/circuit. Changing dimensions or selected values
inside a generated header is insufficient. This release distributes frozen
validated headers, not a general automatic circuit-to-bitstream toolchain.
