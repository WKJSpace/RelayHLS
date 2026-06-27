#!/usr/bin/env python3
import argparse
import csv
import importlib.util
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAKE_GENERATOR = ROOT / "tools" / "generate_fake_h_constants.py"
DEFAULT_CONFIG_PATH = ROOT / "configs" / "constants_config.json"
CONSTANTS = ROOT / "src" / "constants.h"


def _load_fake_generator():
    spec = importlib.util.spec_from_file_location("generate_fake_h_constants", FAKE_GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fake = _load_fake_generator()


class CircuitGraph(object):
    def __init__(self, num_detectors, num_faults, edges, logical_edges=None, priors=None):
        self.num_detectors = int(num_detectors)
        self.num_faults = int(num_faults)
        self.edges = [(int(det), int(fault)) for det, fault in edges]
        self.logical_edges = [(int(obs), int(fault)) for obs, fault in (logical_edges or [])]
        self.priors = [float(value) for value in (priors or [])]


def _infer_shape(edges, logical_edges=None):
    max_detector = max((det for det, _ in edges), default=-1)
    max_fault_from_h = max((fault for _, fault in edges), default=-1)
    max_fault_from_a = max((fault for _, fault in (logical_edges or [])), default=-1)
    return max_detector + 1, max(max_fault_from_h, max_fault_from_a) + 1


def parse_csv_text(text):
    rows = list(csv.reader(io.StringIO(text)))
    rows = [row for row in rows if row and not row[0].strip().startswith("#")]
    if not rows:
        return CircuitGraph(0, 0, [], [], [])

    first = [cell.strip().lower() for cell in rows[0]]
    has_header = "detector" in first and "fault" in first
    if has_header:
        det_idx = first.index("detector")
        fault_idx = first.index("fault")
        data_rows = rows[1:]
    else:
        det_idx = 0
        fault_idx = 1
        data_rows = rows

    edges = []
    for line_no, row in enumerate(data_rows, start=2 if has_header else 1):
        if len(row) <= max(det_idx, fault_idx):
            raise ValueError("CSV line %d must contain detector and fault columns" % line_no)
        edges.append((int(row[det_idx]), int(row[fault_idx])))
    num_detectors, num_faults = _infer_shape(edges)
    return CircuitGraph(num_detectors, num_faults, edges, [], [])


def parse_json_text(text):
    data = json.loads(text)
    edges = [(int(det), int(fault)) for det, fault in data.get("edges", [])]
    logical_edges = [
        (int(obs), int(fault)) for obs, fault in data.get("logical_edges", [])
    ]
    inferred_detectors, inferred_faults = _infer_shape(edges, logical_edges)
    return CircuitGraph(
        data.get("num_detectors", inferred_detectors),
        data.get("num_faults", inferred_faults),
        edges,
        logical_edges,
        data.get("priors", []),
    )


def parse_dem_text(text):
    edges = []
    logical_edges = []
    priors = []
    fault = 0
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("repeat ") or line.startswith("shift_detectors"):
            raise ValueError(
                "DEM line %d uses repeat/shift_detectors; flatten the DEM before conversion" %
                line_no)
        match = re.match(r"error\(([^)]*)\)\s*(.*)$", line)
        if not match:
            continue
        try:
            priors.append(float(match.group(1)))
        except ValueError:
            priors.append(0.0)
        for token in match.group(2).split():
            if token.startswith("D"):
                edges.append((int(token[1:]), fault))
            elif token.startswith("L"):
                logical_edges.append((int(token[1:]), fault))
        fault += 1
    num_detectors, inferred_faults = _infer_shape(edges, logical_edges)
    return CircuitGraph(num_detectors, max(fault, inferred_faults), edges, logical_edges, priors)


def load_graph(path, file_format="auto"):
    path = Path(path)
    text = path.read_text()
    fmt = file_format
    if fmt == "auto":
        suffix = path.suffix.lower()
        if suffix == ".dem":
            fmt = "dem"
        elif suffix == ".json":
            fmt = "json"
        elif suffix == ".csv":
            fmt = "csv"
        else:
            raise ValueError("cannot infer input format from %s; pass --format" % path)
    if fmt == "dem":
        return parse_dem_text(text)
    if fmt == "json":
        return parse_json_text(text)
    if fmt == "csv":
        return parse_csv_text(text)
    raise ValueError("unsupported input format: %s" % fmt)


def _validate_graph_shape(graph):
    if graph.num_detectors > fake.NUM_DETECTORS:
        raise ValueError(
            "input has %d detectors, but config NUM_DETECTORS is %d" %
            (graph.num_detectors, fake.NUM_DETECTORS))
    if graph.num_faults > fake.NUM_FAULTS:
        raise ValueError(
            "input has %d faults, but config NUM_FAULTS is %d" %
            (graph.num_faults, fake.NUM_FAULTS))

    seen = set()
    for det, fault in graph.edges:
        if det < 0 or det >= fake.NUM_DETECTORS:
            raise ValueError("detector index out of range: %d" % det)
        if fault < 0 or fault >= fake.NUM_FAULTS:
            raise ValueError("fault index out of range: %d" % fault)
        key = (det, fault)
        if key in seen:
            raise ValueError("duplicate H edge detector=%d fault=%d" % key)
        seen.add(key)

    for obs, fault in graph.logical_edges:
        if obs < 0 or obs >= fake.K_OBSERVABLES:
            raise ValueError("logical observable index out of range: %d" % obs)
        if fault < 0 or fault >= fake.NUM_FAULTS:
            raise ValueError("logical fault index out of range: %d" % fault)


def _choose_edge_bank(det, fault, slot, cnu_bank_counts, vnu_bank_counts, bank_counts):
    cnu_group = det // fake.CNU_PARALLEL
    vnu_group = fault // fake.VNU_PARALLEL
    preferred = fake._preferred_bank(det, slot)
    ordered_banks = sorted(
        range(fake.EDGE_BANK_FACTOR),
        key=lambda bank: (bank_counts[bank], (bank - preferred) % fake.EDGE_BANK_FACTOR))

    for bank in ordered_banks:
        if bank_counts[bank] >= fake.EDGE_BANK_DEPTH:
            continue
        if cnu_bank_counts[cnu_group][bank] >= fake.BANK_PORTS:
            continue
        if vnu_bank_counts[vnu_group][bank] >= fake.BANK_PORTS:
            continue
        return bank
    raise ValueError(
        "edge bank conflict: detector=%d fault=%d; try lower CNU/VNU parallelism or renumbering" %
        (det, fault))


def build_real_h(graph, config):
    fake.apply_config(config)
    _validate_graph_shape(graph)
    if not graph.edges:
        raise ValueError("input graph must contain at least one detector-fault edge")
    _apply_real_edge_count(len(graph.edges))

    row_faults = [[] for _ in range(fake.NUM_DETECTORS)]
    col_detectors = [[] for _ in range(fake.NUM_FAULTS)]
    for det, fault in graph.edges:
        row_faults[det].append(fault)
        col_detectors[fault].append(det)

    row_degrees = [len(row) for row in row_faults]
    col_degrees = [len(col) for col in col_detectors]
    if row_degrees and max(row_degrees) > fake.H_MAX_ROW_DEGREE:
        raise ValueError(
            "row degree %d exceeds H_MAX_ROW_DEGREE=%d" %
            (max(row_degrees), fake.H_MAX_ROW_DEGREE))
    if col_degrees and max(col_degrees) > fake.H_MAX_COL_DEGREE:
        raise ValueError(
            "column degree %d exceeds H_MAX_COL_DEGREE=%d" %
            (max(col_degrees), fake.H_MAX_COL_DEGREE))

    cnu_groups = fake._ceil_div(fake.NUM_DETECTORS, fake.CNU_PARALLEL)
    vnu_groups = fake._ceil_div(fake.NUM_FAULTS, fake.VNU_PARALLEL)
    detector_groups = fake._ceil_div(fake.NUM_DETECTORS, fake.CONVERGENCE_PARALLEL)
    cnu_bank_counts = [[0 for _ in range(fake.EDGE_BANK_FACTOR)] for _ in range(cnu_groups)]
    vnu_bank_counts = [[0 for _ in range(fake.EDGE_BANK_FACTOR)] for _ in range(vnu_groups)]
    detector_bank_counts = [[0 for _ in range(fake.PACKED_BANK_FACTOR)] for _ in range(detector_groups)]
    bank_counts = [0 for _ in range(fake.EDGE_BANK_FACTOR)]
    edges_by_row = [[] for _ in range(fake.NUM_DETECTORS)]
    edges_by_col = [[] for _ in range(fake.NUM_FAULTS)]

    edge_idx = 0
    for det, faults in enumerate(row_faults):
        for slot, fault in enumerate(sorted(faults)):
            detector_group = det // fake.CONVERGENCE_PARALLEL
            detector_bank = fault % fake.PACKED_BANK_FACTOR
            if detector_bank_counts[detector_group][detector_bank] >= fake.BANK_PORTS:
                raise ValueError(
                    "detector bank conflict: group=%d bank=%d exceeds %d ports; renumber fault columns or reduce CONVERGENCE_PARALLEL" %
                    (detector_group, detector_bank, fake.BANK_PORTS))

            bank = _choose_edge_bank(det, fault, slot, cnu_bank_counts, vnu_bank_counts, bank_counts)
            addr = bank_counts[bank]
            edge = fake.Edge(edge_idx, det, fault, bank, addr)
            edges_by_row[det].append(edge)
            edges_by_col[fault].append(edge)

            bank_counts[bank] += 1
            cnu_bank_counts[det // fake.CNU_PARALLEL][bank] += 1
            vnu_bank_counts[fault // fake.VNU_PARALLEL][bank] += 1
            detector_bank_counts[detector_group][detector_bank] += 1
            edge_idx += 1

    matrix = fake.FakeH(
        fake.NUM_DETECTORS,
        fake.NUM_FAULTS,
        edge_idx,
        row_degrees,
        col_degrees,
        edges_by_row,
        edges_by_col,
    )
    fake.check_bank_conflicts(matrix)
    return matrix


def _apply_real_edge_count(num_edges):
    fake.NUM_EDGES = int(num_edges)
    fake.EDGE_BANK_DEPTH = fake._ceil_div(fake.NUM_EDGES, fake.EDGE_BANK_FACTOR)


def render_real_preamble(config, matrix, logical_nonzeros):
    fake.apply_config(config)
    _apply_real_edge_count(matrix.num_edges)
    a_num_nonzeros = max(1, logical_nonzeros)
    return "\n".join([
        "#ifndef CONSTANTS_H",
        "#define CONSTANTS_H",
        "",
        "// Generated by tools/generate_real_circuit_constants.py.",
        "// Input graph comes from a quantum-circuit simulator result.",
        "",
        "constexpr int PHYSICAL_QUBITS = %d;" % fake.PHYSICAL_QUBITS,
        "constexpr int LOGICAL_QUBITS  = %d;" % fake.LOGICAL_QUBITS,
        "",
        "constexpr int WINDOW_W      = %d;" % fake.WINDOW_W,
        "constexpr int COMMIT_C      = %d;" % fake.COMMIT_C,
        "constexpr int M_PER_CYCLE   = %d;" % fake.M_PER_CYCLE,
        "constexpr int NUM_DETECTORS = WINDOW_W * M_PER_CYCLE;  // %d" % fake.NUM_DETECTORS,
        "constexpr int NUM_FAULTS    = %d;" % fake.NUM_FAULTS,
        "constexpr int K_OBSERVABLES = LOGICAL_QUBITS;",
        "",
        "constexpr int H_AVG_ROW_DEGREE_EXAMPLE = %d;" % fake.ROW_DEGREE,
        "constexpr int NUM_NONZEROS = %d;" % matrix.num_edges,
        "constexpr int NUM_EDGES    = NUM_NONZEROS;",
        "",
        "constexpr int W = WINDOW_W;",
        "constexpr int C = COMMIT_C;",
        "constexpr int FIFO_DEPTH = WINDOW_W + 2;",
        "",
        "constexpr int H_MAX_ROW_DEGREE = %d;" % fake.H_MAX_ROW_DEGREE,
        "constexpr int H_MAX_COL_DEGREE = %d;" % fake.H_MAX_COL_DEGREE,
        "constexpr int A_MAX_ROW_DEGREE = %d;" % fake.A_MAX_ROW_DEGREE,
        "",
        "constexpr int PACK_BITS          = %d;" % fake.PACK_BITS,
        "constexpr int NUM_DETECTOR_WORDS = (NUM_DETECTORS + PACK_BITS - 1) / PACK_BITS;",
        "constexpr int NUM_FAULT_WORDS    = (NUM_FAULTS + PACK_BITS - 1) / PACK_BITS;",
        "constexpr int CARRY_WORDS        = (M_PER_CYCLE + PACK_BITS - 1) / PACK_BITS;",
        "",
        "constexpr int EDGE_BANK_FACTOR      = %d;" % fake.EDGE_BANK_FACTOR,
        "constexpr int EDGE_BANK_DEPTH       = (NUM_EDGES + EDGE_BANK_FACTOR - 1) / EDGE_BANK_FACTOR;",
        "constexpr int PRIOR_BANK_FACTOR     = %d;" % fake.PRIOR_BANK_FACTOR,
        "constexpr int PRIOR_BANK_DEPTH      = (NUM_FAULTS + PRIOR_BANK_FACTOR - 1) / PRIOR_BANK_FACTOR;",
        "constexpr int POSTERIOR_BANK_FACTOR = %d;" % fake.POSTERIOR_BANK_FACTOR,
        "constexpr int PACKED_BANK_FACTOR    = %d;" % fake.PACKED_BANK_FACTOR,
        "",
        "constexpr int CNU_PARALLEL = %d;" % fake.CNU_PARALLEL,
        "constexpr int VNU_PARALLEL = %d;" % fake.VNU_PARALLEL,
        "constexpr int CONVERGENCE_PARALLEL = %d;" % fake.CONVERGENCE_PARALLEL,
        "",
        "constexpr int MSG_INT_BITS = %d;" % fake.MSG_INT_BITS,
        "constexpr int MSG_MAX_MAG  = (1 << MSG_INT_BITS) - 1;",
        "constexpr int PRIOR_PACK_FACTOR = %d;" % fake.PRIOR_PACK_FACTOR,
        "constexpr int PRIOR_WORD_BITS   = 6 * PRIOR_PACK_FACTOR;",
        "constexpr float SCALE_S = %.1ff;" % (float(fake.SCALE_S_FIXED) / float(fake.SCALE_ONE_FIXED)),
        "constexpr int SCALE_FRAC_BITS = %d;" % fake.SCALE_FRAC_BITS,
        "constexpr int SCALE_ONE_FIXED = 1 << SCALE_FRAC_BITS;",
        "constexpr int SCALE_S_FIXED   = %d;" % fake.SCALE_S_FIXED,
        "constexpr int POST_EXTRA_BITS = %d;" % fake.POST_EXTRA_BITS,
        "constexpr int POST_MAG_BITS   = MSG_INT_BITS + POST_EXTRA_BITS;",
        "constexpr int POST_TOTAL_BITS = POST_MAG_BITS + 1;",
        "",
        "constexpr int MEM_SHIFT = %d;" % fake.MEM_SHIFT,
        "constexpr int MEM_SCALE = 1 << MEM_SHIFT;",
        "constexpr int MAX_LEGS = %d;" % fake.MAX_LEGS,
        "constexpr int GAMMA_NUM[MAX_LEGS] = {1, 3, 5, 7};",
        "constexpr int LEG_BETA[MAX_LEGS]  = {7, 5, 3, 1};",
        "constexpr int ALPHA_SHIFT_MAX = 4;",
        "constexpr int MAX_ITERS_PER_LEG = %d;" % fake.MAX_ITERS_PER_LEG,
        "constexpr int GLOBAL_MAX_ITERS = %d;" % fake.GLOBAL_MAX_ITERS,
        "constexpr int CONVERGENCE_CHECK_INTERVAL = %d;" % fake.CONVERGENCE_CHECK_INTERVAL,
        "constexpr int MAX_SOLUTIONS = %d;" % fake.MAX_SOLUTIONS,
        "constexpr int MAX_TOTAL_ITERS = MAX_LEGS * MAX_ITERS_PER_LEG;",
        "",
        "constexpr int WEIGHT_BITS = %d;" % fake.WEIGHT_BITS,
        "constexpr int WEIGHT_MAX  = (1 << WEIGHT_BITS) - 1;",
        "",
        "constexpr int CARRY_DETECTOR_START = COMMIT_C * M_PER_CYCLE;  // %d" % fake.CARRY_DETECTOR_START,
        "constexpr int CARRY_SIZE           = M_PER_CYCLE;             // %d" % fake.CARRY_SIZE,
        "",
        "constexpr int A_NUM_NONZEROS = %d;" % a_num_nonzeros,
        "",
        "static_assert(NUM_DETECTORS == WINDOW_W * M_PER_CYCLE, \"detector count must match window geometry\");",
        "static_assert(NUM_EDGES == NUM_NONZEROS, \"edge count alias mismatch\");",
        "static_assert(PACK_BITS > 0, \"PACK_BITS must be positive\");",
        "static_assert((PACK_BITS % VNU_PARALLEL) == 0, \"VNU_PARALLEL must divide PACK_BITS\");",
        "static_assert(PACKED_BANK_FACTOR == PACK_BITS, \"packed detector banks must match PACK_BITS\");",
        "static_assert(PRIOR_PACK_FACTOR == PACK_BITS, \"prior ABI must pack one value per bit lane\");",
        "static_assert(PRIOR_BANK_FACTOR == PRIOR_PACK_FACTOR, \"prior banks must match prior pack lanes\");",
        "static_assert(EDGE_BANK_FACTOR >= CNU_PARALLEL * 2, \"CNU schedule assumes enough dual-port edge banks\");",
        "static_assert(EDGE_BANK_FACTOR >= VNU_PARALLEL, \"VNU schedule assumes enough edge banks\");",
        "static_assert(GLOBAL_MAX_ITERS <= MAX_TOTAL_ITERS, \"global iteration budget exceeds LEG budget\");",
        "static_assert(CONVERGENCE_CHECK_INTERVAL > 0, \"convergence interval must be positive\");",
        "static_assert(CARRY_DETECTOR_START + CARRY_SIZE <= NUM_DETECTORS, \"carry window exceeds detector window\");",
        "",
    ]) + "\n"


def render_real_tail(graph):
    logical_rows = [[] for _ in range(fake.K_OBSERVABLES)]
    for obs, fault in graph.logical_edges:
        logical_rows[obs].append(fault)
    if any(len(row) > fake.A_MAX_ROW_DEGREE for row in logical_rows):
        raise ValueError("logical observable row degree exceeds A_MAX_ROW_DEGREE")

    a_row_degrees = [len(row) for row in logical_rows]
    a_neighbors = [fake._pad(sorted(row), fake.A_MAX_ROW_DEGREE) for row in logical_rows]
    a_csr_row_ptr = [0]
    a_csr_col_idx = []
    for row in logical_rows:
        a_csr_col_idx.extend(sorted(row))
        a_csr_row_ptr.append(len(a_csr_col_idx))
    if not a_csr_col_idx:
        a_csr_col_idx = [0]

    return "\n".join([
        "// ================================================================",
        "// Runtime priors",
        "// ================================================================",
        "// The HLS top uses packed prior input words. PRIOR_INIT remains only",
        "// for compatibility with code paths that include constants.h directly.",
        "constexpr int PRIOR_INIT[NUM_FAULTS] = {};",
        "",
        "// ================================================================",
        "// A~ logical action matrix",
        "// ================================================================",
        fake._format_flat_array("A_ROW_DEGREES", "K_OBSERVABLES", a_row_degrees),
        "",
        fake._format_2d_array("A_ROW_NEIGHBORS", "K_OBSERVABLES][A_MAX_ROW_DEGREE", a_neighbors),
        "",
        fake._format_flat_array("A_CSR_ROW_PTR", "K_OBSERVABLES + 1", a_csr_row_ptr),
        "",
        fake._format_flat_array("A_CSR_COL_IDX", "A_NUM_NONZEROS", a_csr_col_idx),
        "",
        "// ================================================================",
        "// Dummy masks",
        "// ================================================================",
        "constexpr int COMMIT_MASK[NUM_FAULTS] = {};",
        "constexpr int CONVERGENCE_MASK[NUM_DETECTORS] = {};",
        "",
        "// Carry-out rows",
        "constexpr int CARRY_OUT_ROWS[CARRY_SIZE] = {};",
        "",
        "#endif  // CONSTANTS_H",
        "",
    ])


def render_real_constants(config, graph, matrix):
    fake.apply_config(config)
    _apply_real_edge_count(matrix.num_edges)
    logical_nonzeros = len(graph.logical_edges)
    preamble = render_real_preamble(config, matrix, logical_nonzeros)
    _apply_real_edge_count(matrix.num_edges)
    generated = fake.render_generated_section(matrix).replace(
        "// Deterministic fake sparse matrix for HLS resource/performance testing.",
        "// Sparse detector-fault matrix imported from a quantum-circuit simulator.")
    generated = generated.replace(
        "// Rows have degree %d; columns are capped at H_MAX_COL_DEGREE." % fake.ROW_DEGREE,
        "// Rows have real circuit degrees; columns are capped at H_MAX_COL_DEGREE.")
    return (
        preamble + "\n" + generated + "\n" + render_real_tail(graph))


def _load_config(path):
    path = Path(path)
    if path.exists():
        return fake.load_config(path)
    return fake.normalize_config(fake.DEFAULT_CONFIG)


def _print_summary(path, graph, matrix):
    active_faults = sum(1 for degree in matrix.col_degrees if degree > 0)
    checks = fake.check_bank_conflicts(matrix)
    print("constants=%s" % path)
    print("input_detectors=%d input_faults=%d edges=%d active_faults=%d" %
          (graph.num_detectors, graph.num_faults, matrix.num_edges, active_faults))
    print("cnu_max_bank_accesses=%d vnu_max_bank_accesses=%d detector_max_bank_accesses=%d" %
          (checks["cnu_max_bank_accesses"],
           checks["vnu_max_bank_accesses"],
           checks["detector_max_bank_accesses"]))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate Relay-BP constants.h from a real quantum-circuit detector graph.")
    parser.add_argument("--input", required=True, help="simulator output: .dem, .json, or .csv")
    parser.add_argument(
        "--format", default="auto", choices=("auto", "dem", "json", "csv"),
        help="input format; default infers from file suffix")
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH),
        help="constants JSON config path")
    parser.add_argument(
        "--output", default=str(CONSTANTS),
        help="constants.h output path")
    parser.add_argument(
        "--check", action="store_true",
        help="validate graph, degrees, and bank schedules without writing constants.h")
    args = parser.parse_args(argv)

    config = _load_config(args.config)
    graph = load_graph(args.input, args.format)
    matrix = build_real_h(graph, config)
    if args.check:
        print("check passed; no constants.h written")
    else:
        Path(args.output).write_text(render_real_constants(config, graph, matrix))
        print("wrote %s" % args.output)
    _print_summary(args.output, graph, matrix)


if __name__ == "__main__":
    main()
