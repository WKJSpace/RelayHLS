#!/usr/bin/env python3
import argparse
import json
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTANTS = ROOT / "src" / "constants.h"
DEFAULT_CONFIG_PATH = ROOT / "configs" / "constants_config.json"

BASE_CONFIG = {
    "PHYSICAL_QUBITS": 144,
    "LOGICAL_QUBITS": 12,
    "WINDOW_W": 12,
    "COMMIT_C": 1,
    "M_PER_CYCLE": 84,
    "NUM_FAULTS": 9000,
    "ROW_DEGREE": 8,
    "H_MAX_ROW_DEGREE": 16,
    "H_MAX_COL_DEGREE": 8,
    "A_MAX_ROW_DEGREE": 64,
    "PACK_BITS": 64,
    "EDGE_BANK_FACTOR": 64,
    "PRIOR_BANK_FACTOR": 64,
    "POSTERIOR_BANK_FACTOR": 64,
    "PACKED_BANK_FACTOR": 64,
    "BANK_PORTS": 2,
    "CNU_PARALLEL": 16,
    "VNU_PARALLEL": 32,
    "CONVERGENCE_PARALLEL": 16,
    "MSG_INT_BITS": 4,
    "PRIOR_PACK_FACTOR": 64,
    "SCALE_FRAC_BITS": 8,
    "SCALE_S_FIXED": 512,
    "POST_EXTRA_BITS": 3,
    "MEM_SHIFT": 3,
    "MAX_LEGS": 4,
    "MAX_ITERS_PER_LEG": 10,
    "GLOBAL_MAX_ITERS": 10,
    "CONVERGENCE_CHECK_INTERVAL": 2,
    "MAX_SOLUTIONS": 2,
    "WEIGHT_BITS": 20,
    "A_NUM_NONZEROS": 1,
}

PROJECT_VARIANTS = {
    "RelayBP_pack64_c8_v16": {
        "CNU_PARALLEL": 8,
        "VNU_PARALLEL": 16,
        "CONVERGENCE_PARALLEL": 8,
    },
    "RelayBP_pack64_c16_v16": {
        "CNU_PARALLEL": 16,
        "VNU_PARALLEL": 16,
        "CONVERGENCE_PARALLEL": 16,
    },
    "RelayBP_pack64_c16_v32": {
        "CNU_PARALLEL": 16,
        "VNU_PARALLEL": 32,
        "CONVERGENCE_PARALLEL": 16,
    },
}

PROMPT_FIELDS = [
    "WINDOW_W",
    "M_PER_CYCLE",
    "NUM_FAULTS",
    "ROW_DEGREE",
    "H_MAX_ROW_DEGREE",
    "H_MAX_COL_DEGREE",
    "PACK_BITS",
    "EDGE_BANK_FACTOR",
    "PRIOR_BANK_FACTOR",
    "PACKED_BANK_FACTOR",
    "CNU_PARALLEL",
    "VNU_PARALLEL",
    "CONVERGENCE_PARALLEL",
    "MAX_ITERS_PER_LEG",
    "GLOBAL_MAX_ITERS",
    "CONVERGENCE_CHECK_INTERVAL",
]

PARAMETER_HINTS = {
    "WINDOW_W": "Detector window width. IBM-sized setup uses 12, so NUM_DETECTORS becomes 12 * 84 = 1008.",
    "M_PER_CYCLE": "Detectors per syndrome cycle. Keep 84 for the current Gross-code/IBM comparison.",
    "NUM_FAULTS": "Fault candidates. Current evaluation uses 9000.",
    "ROW_DEGREE": "Synthetic H row degree. Must be <= H_MAX_ROW_DEGREE; current generated H uses 8.",
    "H_MAX_ROW_DEGREE": "Storage slots per detector row. Must cover ROW_DEGREE; current kernels assume room for 16.",
    "H_MAX_COL_DEGREE": "Storage slots per fault column. Must be high enough for generation; current cap is 8.",
    "PACK_BITS": "Packed syndrome/prior word width. Must be positive and divisible by VNU_PARALLEL; current value is 64.",
    "EDGE_BANK_FACTOR": "Number of edge-message banks. Current schedules are built for 64 banks.",
    "PRIOR_BANK_FACTOR": "Prior cache banks. Usually keep equal to PRIOR_PACK_FACTOR/PACK_BITS at 64.",
    "PACKED_BANK_FACTOR": "Detector/posterior packed banks. Keep equal to PACK_BITS for the current banking equations.",
    "CNU_PARALLEL": "Check-node lanes. Valid examples: 8 or 16. Higher values need bank-conflict validation.",
    "VNU_PARALLEL": "Variable-node lanes. Must divide PACK_BITS. Valid examples: 16 or 32.",
    "CONVERGENCE_PARALLEL": "Detector convergence lanes. Usually match CNU_PARALLEL for balanced detector banking.",
    "MAX_ITERS_PER_LEG": "Per-LEG safety cap. Current IBM-comparison design keeps 10.",
    "GLOBAL_MAX_ITERS": "Total BP iterations across all 4 LEG strengths. IBM criterion here is 10.",
    "CONVERGENCE_CHECK_INTERVAL": "Check interval in iterations. Current design checks every 2 iterations.",
}

DEFAULT_CONFIG = dict(BASE_CONFIG)
DEFAULT_CONFIG.update(PROJECT_VARIANTS.get(ROOT.name, {}))

PHYSICAL_QUBITS = 0
LOGICAL_QUBITS = 0
WINDOW_W = 0
COMMIT_C = 0
M_PER_CYCLE = 0
NUM_DETECTORS = 0
NUM_FAULTS = 0
K_OBSERVABLES = 0
ROW_DEGREE = 0
NUM_EDGES = 0
PACK_BITS = 0
NUM_DETECTOR_WORDS = 0
NUM_FAULT_WORDS = 0
CARRY_WORDS = 0
EDGE_BANK_FACTOR = 0
EDGE_BANK_DEPTH = 0
PRIOR_BANK_FACTOR = 0
PRIOR_BANK_DEPTH = 0
POSTERIOR_BANK_FACTOR = 0
PACKED_BANK_FACTOR = 0
BANK_PORTS = 0
CNU_PARALLEL = 0
VNU_PARALLEL = 0
CONVERGENCE_PARALLEL = 0
H_MAX_ROW_DEGREE = 0
H_MAX_COL_DEGREE = 0
A_MAX_ROW_DEGREE = 0
MSG_INT_BITS = 0
PRIOR_PACK_FACTOR = 0
PRIOR_WORD_BITS = 0
SCALE_FRAC_BITS = 0
SCALE_ONE_FIXED = 0
SCALE_S_FIXED = 0
POST_EXTRA_BITS = 0
POST_MAG_BITS = 0
POST_TOTAL_BITS = 0
MEM_SHIFT = 0
MEM_SCALE = 0
MAX_LEGS = 0
MAX_ITERS_PER_LEG = 0
GLOBAL_MAX_ITERS = 0
CONVERGENCE_CHECK_INTERVAL = 0
MAX_SOLUTIONS = 0
MAX_TOTAL_ITERS = 0
WEIGHT_BITS = 0
CARRY_DETECTOR_START = 0
CARRY_SIZE = 0
A_NUM_NONZEROS = 0

Edge = namedtuple("Edge", "edge_idx check_idx var_idx bank addr")
ScheduledEdge = namedtuple("ScheduledEdge", "valid edge lane slot")


def _ceil_div(value, divisor):
    return (value + divisor - 1) // divisor


def _is_power_of_two(value):
    return value > 0 and (value & (value - 1)) == 0


def normalize_config(config):
    normalized = dict(DEFAULT_CONFIG)
    normalized.update(config or {})
    unknown = sorted(set(normalized) - set(BASE_CONFIG))
    if unknown:
        raise ValueError("unknown config keys: %s" % ", ".join(unknown))
    for key, value in list(normalized.items()):
        if isinstance(value, bool):
            raise ValueError("%s must be an integer, not bool" % key)
        try:
            normalized[key] = int(value)
        except (TypeError, ValueError):
            raise ValueError("%s must be an integer" % key)
    return normalized


def validate_config(config):
    cfg = normalize_config(config)
    errors = []

    for key, value in sorted(cfg.items()):
        if value <= 0:
            errors.append("%s must be positive" % key)

    if cfg["WINDOW_W"] < cfg["COMMIT_C"]:
        errors.append("WINDOW_W must be >= COMMIT_C")
    if cfg["ROW_DEGREE"] > cfg["H_MAX_ROW_DEGREE"]:
        errors.append("ROW_DEGREE must be <= H_MAX_ROW_DEGREE")
    if cfg["PACK_BITS"] % cfg["VNU_PARALLEL"] != 0:
        errors.append("VNU_PARALLEL must divide PACK_BITS")
    if cfg["PACKED_BANK_FACTOR"] != cfg["PACK_BITS"]:
        errors.append("PACKED_BANK_FACTOR must equal PACK_BITS for detector banking")
    if cfg["PRIOR_PACK_FACTOR"] != cfg["PACK_BITS"]:
        errors.append("PRIOR_PACK_FACTOR must equal PACK_BITS for the packed-prior ABI")
    if cfg["PRIOR_BANK_FACTOR"] != cfg["PRIOR_PACK_FACTOR"]:
        errors.append("PRIOR_BANK_FACTOR should equal PRIOR_PACK_FACTOR to keep one prior word banked by lane")
    if cfg["EDGE_BANK_FACTOR"] < cfg["CNU_PARALLEL"] * cfg["BANK_PORTS"]:
        errors.append("EDGE_BANK_FACTOR must be at least CNU_PARALLEL * BANK_PORTS")
    if cfg["EDGE_BANK_FACTOR"] < cfg["VNU_PARALLEL"]:
        errors.append("EDGE_BANK_FACTOR must be at least VNU_PARALLEL")
    if cfg["PACK_BITS"] < cfg["VNU_PARALLEL"]:
        errors.append("PACK_BITS must be >= VNU_PARALLEL")
    if not _is_power_of_two(cfg["PACK_BITS"]):
        errors.append("PACK_BITS should be a power of two")
    if cfg["BANK_PORTS"] != 2:
        errors.append("BANK_PORTS must remain 2 for true dual-port BRAM scheduling")
    if cfg["GLOBAL_MAX_ITERS"] > cfg["MAX_LEGS"] * cfg["MAX_ITERS_PER_LEG"]:
        errors.append("GLOBAL_MAX_ITERS cannot exceed MAX_LEGS * MAX_ITERS_PER_LEG")
    if cfg["CONVERGENCE_CHECK_INTERVAL"] > cfg["GLOBAL_MAX_ITERS"]:
        errors.append("CONVERGENCE_CHECK_INTERVAL cannot exceed GLOBAL_MAX_ITERS")
    if cfg["MSG_INT_BITS"] < 2:
        errors.append("MSG_INT_BITS must be at least 2")
    if cfg["SCALE_S_FIXED"] <= (1 << cfg["SCALE_FRAC_BITS"]):
        errors.append("SCALE_S_FIXED should be larger than 1.0 in fixed-point units")
    if cfg["WEIGHT_BITS"] >= 31:
        errors.append("WEIGHT_BITS must stay below 31 for int-based weight arithmetic")

    num_detectors = cfg["WINDOW_W"] * cfg["M_PER_CYCLE"]
    carry_start = cfg["COMMIT_C"] * cfg["M_PER_CYCLE"]
    carry_size = cfg["M_PER_CYCLE"]
    if carry_start + carry_size > num_detectors:
        errors.append("COMMIT_C and M_PER_CYCLE make carry rows exceed NUM_DETECTORS")
    if _ceil_div(num_detectors, cfg["PACK_BITS"]) <= 0:
        errors.append("NUM_DETECTOR_WORDS must be nonzero")

    if errors:
        raise ValueError("\n".join(errors))
    return cfg


def apply_config(config):
    cfg = validate_config(config)
    globals_dict = globals()
    for key, value in cfg.items():
        globals_dict[key] = value

    globals_dict["NUM_DETECTORS"] = cfg["WINDOW_W"] * cfg["M_PER_CYCLE"]
    globals_dict["K_OBSERVABLES"] = cfg["LOGICAL_QUBITS"]
    globals_dict["NUM_EDGES"] = NUM_DETECTORS * cfg["ROW_DEGREE"]
    globals_dict["NUM_DETECTOR_WORDS"] = _ceil_div(NUM_DETECTORS, cfg["PACK_BITS"])
    globals_dict["NUM_FAULT_WORDS"] = _ceil_div(cfg["NUM_FAULTS"], cfg["PACK_BITS"])
    globals_dict["CARRY_WORDS"] = _ceil_div(cfg["M_PER_CYCLE"], cfg["PACK_BITS"])
    globals_dict["EDGE_BANK_DEPTH"] = _ceil_div(NUM_EDGES, cfg["EDGE_BANK_FACTOR"])
    globals_dict["PRIOR_BANK_DEPTH"] = _ceil_div(cfg["NUM_FAULTS"], cfg["PRIOR_BANK_FACTOR"])
    globals_dict["PRIOR_WORD_BITS"] = 6 * cfg["PRIOR_PACK_FACTOR"]
    globals_dict["SCALE_ONE_FIXED"] = 1 << cfg["SCALE_FRAC_BITS"]
    globals_dict["POST_MAG_BITS"] = cfg["MSG_INT_BITS"] + cfg["POST_EXTRA_BITS"]
    globals_dict["POST_TOTAL_BITS"] = POST_MAG_BITS + 1
    globals_dict["MEM_SCALE"] = 1 << cfg["MEM_SHIFT"]
    globals_dict["MAX_TOTAL_ITERS"] = cfg["MAX_LEGS"] * cfg["MAX_ITERS_PER_LEG"]
    globals_dict["CARRY_DETECTOR_START"] = cfg["COMMIT_C"] * cfg["M_PER_CYCLE"]
    globals_dict["CARRY_SIZE"] = cfg["M_PER_CYCLE"]
    return cfg


def load_config(path):
    with Path(path).open() as fh:
        return normalize_config(json.load(fh))


def write_config(config, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize_config(config), indent=2, sort_keys=True) + "\n")


def prompt_config(base_config):
    cfg = normalize_config(base_config)
    print("Interactive constants.h configuration")
    print("Press Enter to keep the value shown in brackets.")
    for key in PROMPT_FIELDS:
        while True:
            print("\n%s" % key)
            print("  hint: %s" % PARAMETER_HINTS[key])
            raw = input("  value [%s]: " % cfg[key]).strip()
            if raw:
                try:
                    cfg[key] = int(raw)
                except ValueError:
                    print("  error: enter an integer")
                    continue
            try:
                validate_config(cfg)
            except ValueError as exc:
                print("  invalid setting:")
                for line in str(exc).splitlines():
                    print("    - %s" % line)
                if raw:
                    cfg[key] = normalize_config(base_config)[key]
                continue
            break
    return cfg


apply_config(DEFAULT_CONFIG)


class FakeH(object):
    def __init__(self, num_detectors, num_faults, num_edges, row_degrees, col_degrees, edges_by_row, edges_by_col):
        self.num_detectors = num_detectors
        self.num_faults = num_faults
        self.num_edges = num_edges
        self.row_degrees = row_degrees
        self.col_degrees = col_degrees
        self.edges_by_row = edges_by_row
        self.edges_by_col = edges_by_col


def _preferred_bank(check_idx, slot):
    # Preserve the original CNU-friendly bank order as the starting point.
    lane = check_idx % CNU_PARALLEL
    return (lane + (slot % 4) * CNU_PARALLEL) % EDGE_BANK_FACTOR


def _bank_order(preferred, bank_counts):
    return sorted(
        range(EDGE_BANK_FACTOR),
        key=lambda bank: (bank_counts[bank], (bank - preferred) % EDGE_BANK_FACTOR))


def _try_choose_bank(check_idx, var_idx, slot, cnu_bank_counts, vnu_bank_counts, detector_bank_counts, bank_counts):
    cnu_group = check_idx // CNU_PARALLEL
    vnu_group = var_idx // VNU_PARALLEL
    detector_group = check_idx // CONVERGENCE_PARALLEL
    detector_bank = var_idx % PACKED_BANK_FACTOR
    preferred = _preferred_bank(check_idx, slot)

    if detector_bank_counts[detector_group][detector_bank] >= BANK_PORTS:
        return None

    for bank in _bank_order(preferred, bank_counts):
        if bank_counts[bank] >= EDGE_BANK_DEPTH:
            continue
        if cnu_bank_counts[cnu_group][bank] >= BANK_PORTS:
            continue
        if vnu_bank_counts[vnu_group][bank] >= BANK_PORTS:
            continue
        return bank
    return None


def _choose_var_and_bank(edge_idx, check_idx, slot, col_degrees, row_vars, cnu_bank_counts, vnu_bank_counts, detector_bank_counts, bank_counts):
    var = (edge_idx * 1543 + check_idx * 17 + slot * 9973) % NUM_FAULTS
    for _ in range(NUM_FAULTS):
        if col_degrees[var] < H_MAX_COL_DEGREE and var not in row_vars:
            bank = _try_choose_bank(check_idx, var, slot, cnu_bank_counts, vnu_bank_counts, detector_bank_counts, bank_counts)
            if bank is not None:
                return var, bank
        var = (var + 1) % NUM_FAULTS
    raise RuntimeError(
        "could not place edge without bank conflict: edge=%d check=%d slot=%d" %
        (edge_idx, check_idx, slot))


def build_fake_h():
    row_degrees = [ROW_DEGREE for _ in range(NUM_DETECTORS)]
    col_degrees = [0 for _ in range(NUM_FAULTS)]
    edges_by_row = [[] for _ in range(NUM_DETECTORS)]
    edges_by_col = [[] for _ in range(NUM_FAULTS)]
    bank_counts = [0 for _ in range(EDGE_BANK_FACTOR)]
    cnu_groups = (NUM_DETECTORS + CNU_PARALLEL - 1) // CNU_PARALLEL
    vnu_groups = (NUM_FAULTS + VNU_PARALLEL - 1) // VNU_PARALLEL
    detector_groups = (NUM_DETECTORS + CONVERGENCE_PARALLEL - 1) // CONVERGENCE_PARALLEL
    cnu_bank_counts = [[0 for _ in range(EDGE_BANK_FACTOR)] for _ in range(cnu_groups)]
    vnu_bank_counts = [[0 for _ in range(EDGE_BANK_FACTOR)] for _ in range(vnu_groups)]
    detector_bank_counts = [[0 for _ in range(PACKED_BANK_FACTOR)] for _ in range(detector_groups)]

    edge_idx = 0
    for check_idx in range(NUM_DETECTORS):
        row_vars = set()
        for slot in range(ROW_DEGREE):
            var_idx, bank = _choose_var_and_bank(
                edge_idx, check_idx, slot, col_degrees, row_vars,
                cnu_bank_counts, vnu_bank_counts, detector_bank_counts, bank_counts)
            addr = bank_counts[bank]
            bank_counts[bank] += 1
            cnu_bank_counts[check_idx // CNU_PARALLEL][bank] += 1
            vnu_bank_counts[var_idx // VNU_PARALLEL][bank] += 1
            detector_bank_counts[check_idx // CONVERGENCE_PARALLEL][var_idx % PACKED_BANK_FACTOR] += 1
            edge = Edge(edge_idx, check_idx, var_idx, bank, addr)
            edges_by_row[check_idx].append(edge)
            edges_by_col[var_idx].append(edge)
            row_vars.add(var_idx)
            col_degrees[var_idx] += 1
            edge_idx += 1

    if edge_idx != NUM_EDGES:
        raise AssertionError("expected %d edges, got %d" % (NUM_EDGES, edge_idx))
    if max(col_degrees) > H_MAX_COL_DEGREE:
        raise AssertionError("generated column exceeds H_MAX_COL_DEGREE")
    if max(bank_counts) > EDGE_BANK_DEPTH:
        raise AssertionError("edge bank exceeds EDGE_BANK_DEPTH")

    matrix = FakeH(NUM_DETECTORS, NUM_FAULTS, NUM_EDGES, row_degrees, col_degrees, edges_by_row, edges_by_col)
    check_bank_conflicts(matrix)
    return matrix


def _max_group_bank_count(groups, group_size, edges_for_node):
    max_count = 0
    worst_group = 0
    worst_bank = 0
    for group_base in range(0, groups, group_size):
        counts = [0 for _ in range(EDGE_BANK_FACTOR)]
        for node in range(group_base, min(group_base + group_size, groups)):
            for edge in edges_for_node[node]:
                counts[edge.bank] += 1
        local_max = max(counts)
        if local_max > max_count:
            max_count = local_max
            worst_group = group_base // group_size
            worst_bank = counts.index(local_max)
    return max_count, worst_group, worst_bank


def check_bank_conflicts(matrix):
    cnu_max, cnu_group, cnu_bank = _max_group_bank_count(
        matrix.num_detectors, CNU_PARALLEL, matrix.edges_by_row)
    vnu_max, vnu_group, vnu_bank = _max_group_bank_count(
        matrix.num_faults, VNU_PARALLEL, matrix.edges_by_col)
    detector_max, detector_group, detector_bank = _max_detector_group_bank_count(matrix)
    if cnu_max > BANK_PORTS:
        raise AssertionError(
            "CNU bank conflict: group=%d bank=%d accesses=%d" %
            (cnu_group, cnu_bank, cnu_max))
    if vnu_max > BANK_PORTS:
        raise AssertionError(
            "VNU bank conflict: group=%d bank=%d accesses=%d" %
            (vnu_group, vnu_bank, vnu_max))
    if detector_max > BANK_PORTS:
        raise AssertionError(
            "detector bank conflict: group=%d bank=%d accesses=%d" %
            (detector_group, detector_bank, detector_max))
    return {
        "cnu_max_bank_accesses": cnu_max,
        "vnu_max_bank_accesses": vnu_max,
        "detector_max_bank_accesses": detector_max,
    }


def _max_detector_group_bank_count(matrix):
    max_count = 0
    worst_group = 0
    worst_bank = 0
    for group_base in range(0, matrix.num_detectors, CONVERGENCE_PARALLEL):
        counts = [0 for _ in range(PACKED_BANK_FACTOR)]
        for check_idx in range(group_base, min(group_base + CONVERGENCE_PARALLEL, matrix.num_detectors)):
            for edge in matrix.edges_by_row[check_idx]:
                counts[edge.var_idx % PACKED_BANK_FACTOR] += 1
        local_max = max(counts)
        if local_max > max_count:
            max_count = local_max
            worst_group = group_base // CONVERGENCE_PARALLEL
            worst_bank = counts.index(local_max)
    return max_count, worst_group, worst_bank


def build_prior_bank_map():
    return [(j % PRIOR_BANK_FACTOR, j // PRIOR_BANK_FACTOR) for j in range(NUM_FAULTS)]


def build_active_faults(matrix):
    return [j for j, degree in enumerate(matrix.col_degrees) if degree > 0]


def build_bank_major_schedule(node_count, group_size, edges_by_node, group_count=None):
    minimum_group_count = (node_count + group_size - 1) // group_size
    if group_count is None:
        group_count = minimum_group_count
    if group_count < minimum_group_count:
        raise AssertionError("schedule has fewer groups than required")
    schedule = []
    for group in range(group_count):
        banks = [[] for _ in range(EDGE_BANK_FACTOR)]
        group_base = group * group_size
        for node in range(group_base, min(group_base + group_size, node_count)):
            lane = node - group_base
            for slot, edge in enumerate(edges_by_node[node]):
                banks[edge.bank].append(
                    ScheduledEdge(True, edge, lane, slot))

        padded_banks = []
        for bank, entries in enumerate(banks):
            if len(entries) > BANK_PORTS:
                raise AssertionError(
                    "bank-major schedule conflict: group=%d bank=%d accesses=%d" %
                    (group, bank, len(entries)))
            padded_banks.append(
                entries + [ScheduledEdge(False, None, 0, 0)] * (BANK_PORTS - len(entries)))
        schedule.append(padded_banks)
    return schedule


def build_lane_slot_schedule(node_count, group_size, max_degree, edges_by_node, group_count=None):
    minimum_group_count = (node_count + group_size - 1) // group_size
    if group_count is None:
        group_count = minimum_group_count
    if group_count < minimum_group_count:
        raise AssertionError("schedule has fewer groups than required")
    schedule = []
    for group in range(group_count):
        lanes = []
        group_base = group * group_size
        bank_counts = [0 for _ in range(EDGE_BANK_FACTOR)]
        for lane in range(group_size):
            node = group_base + lane
            entries = []
            if node < node_count:
                node_edges = edges_by_node[node]
                if len(node_edges) > max_degree:
                    raise AssertionError("node degree exceeds max_degree")
                for slot, edge in enumerate(node_edges):
                    bank_counts[edge.bank] += 1
                    entries.append(ScheduledEdge(True, edge, lane, slot))
            entries.extend([ScheduledEdge(False, None, lane, len(entries))]
                           * (max_degree - len(entries)))
            lanes.append(entries)
        for bank, count in enumerate(bank_counts):
            if count > BANK_PORTS:
                raise AssertionError(
                    "lane-slot schedule conflict: group=%d bank=%d accesses=%d" %
                    (group, bank, count))
        schedule.append(lanes)
    return schedule


def build_detector_schedule(matrix):
    schedule = []
    group_count = (matrix.num_detectors + CONVERGENCE_PARALLEL - 1) // CONVERGENCE_PARALLEL
    for group in range(group_count):
        banks = [[] for _ in range(PACKED_BANK_FACTOR)]
        group_base = group * CONVERGENCE_PARALLEL
        for check_idx in range(group_base, min(group_base + CONVERGENCE_PARALLEL, matrix.num_detectors)):
            lane = check_idx - group_base
            for slot, edge in enumerate(matrix.edges_by_row[check_idx]):
                bank = edge.var_idx % PACKED_BANK_FACTOR
                banks[bank].append(ScheduledEdge(True, edge, lane, slot))

        padded_banks = []
        for bank, entries in enumerate(banks):
            if len(entries) > BANK_PORTS:
                raise AssertionError(
                    "detector schedule conflict: group=%d bank=%d accesses=%d" %
                    (group, bank, len(entries)))
            padded_banks.append(
                entries + [ScheduledEdge(False, None, 0, 0)] * (BANK_PORTS - len(entries)))
        schedule.append(padded_banks)
    return schedule


def _chunks(values, width):
    for i in range(0, len(values), width):
        yield values[i:i + width]


def _format_flat_array(name, size, values, width=16):
    lines = ["constexpr int %s[%s] = {" % (name, size)]
    for chunk in _chunks(values, width):
        lines.append("    " + ", ".join(str(v) for v in chunk) + ",")
    lines.append("};")
    return "\n".join(lines)


def _format_2d_array(name, size, values):
    lines = ["constexpr int %s[%s] = {" % (name, size)]
    for row in values:
        lines.append("    {" + ", ".join(str(v) for v in row) + "},")
    lines.append("};")
    return "\n".join(lines)


def _format_3d_array(name, size, values):
    lines = ["constexpr int %s[%s] = {" % (name, size)]
    for group in values:
        lines.append("    {")
        for row in group:
            lines.append("        {" + ", ".join(str(v) for v in row) + "},")
        lines.append("    },")
    lines.append("};")
    return "\n".join(lines)


def _pad(values, size):
    if len(values) > size:
        raise AssertionError("cannot pad %d values into size %d" % (len(values), size))
    return list(values) + [0] * (size - len(values))


def render_preamble():
    return "\n".join([
        "#ifndef CONSTANTS_H",
        "#define CONSTANTS_H",
        "",
        "// Generated by tools/generate_fake_h_constants.py.",
        "// Edit configs/constants_config.json and regenerate instead of hand-editing this file.",
        "",
        "// Code parameters",
        "constexpr int PHYSICAL_QUBITS = %d;" % PHYSICAL_QUBITS,
        "constexpr int LOGICAL_QUBITS  = %d;" % LOGICAL_QUBITS,
        "",
        "// Sliding-window parameters",
        "constexpr int WINDOW_W      = %d;" % WINDOW_W,
        "constexpr int COMMIT_C      = %d;" % COMMIT_C,
        "constexpr int M_PER_CYCLE   = %d;" % M_PER_CYCLE,
        "constexpr int NUM_DETECTORS = WINDOW_W * M_PER_CYCLE;  // %d" % NUM_DETECTORS,
        "constexpr int NUM_FAULTS    = %d;" % NUM_FAULTS,
        "constexpr int K_OBSERVABLES = LOGICAL_QUBITS;",
        "",
        "// Synthetic H dimensions",
        "constexpr int H_AVG_ROW_DEGREE_EXAMPLE = %d;" % ROW_DEGREE,
        "constexpr int NUM_NONZEROS = NUM_DETECTORS * H_AVG_ROW_DEGREE_EXAMPLE;  // %d" % NUM_EDGES,
        "constexpr int NUM_EDGES    = NUM_NONZEROS;",
        "",
        "// Decoder constants",
        "constexpr int W = WINDOW_W;",
        "constexpr int C = COMMIT_C;",
        "constexpr int FIFO_DEPTH = WINDOW_W + 2;",
        "",
        "// Matrix degree caps",
        "constexpr int H_MAX_ROW_DEGREE = %d;" % H_MAX_ROW_DEGREE,
        "constexpr int H_MAX_COL_DEGREE = %d;" % H_MAX_COL_DEGREE,
        "constexpr int A_MAX_ROW_DEGREE = %d;" % A_MAX_ROW_DEGREE,
        "",
        "// Packed vector parameters",
        "constexpr int PACK_BITS          = %d;" % PACK_BITS,
        "constexpr int NUM_DETECTOR_WORDS = (NUM_DETECTORS + PACK_BITS - 1) / PACK_BITS;",
        "constexpr int NUM_FAULT_WORDS    = (NUM_FAULTS + PACK_BITS - 1) / PACK_BITS;",
        "constexpr int CARRY_WORDS        = (M_PER_CYCLE + PACK_BITS - 1) / PACK_BITS;",
        "",
        "// Banked edge-message and prior memories",
        "constexpr int EDGE_BANK_FACTOR      = %d;" % EDGE_BANK_FACTOR,
        "constexpr int EDGE_BANK_DEPTH       = (NUM_EDGES + EDGE_BANK_FACTOR - 1) / EDGE_BANK_FACTOR;",
        "constexpr int PRIOR_BANK_FACTOR     = %d;" % PRIOR_BANK_FACTOR,
        "constexpr int PRIOR_BANK_DEPTH      = (NUM_FAULTS + PRIOR_BANK_FACTOR - 1) / PRIOR_BANK_FACTOR;",
        "constexpr int POSTERIOR_BANK_FACTOR = %d;" % POSTERIOR_BANK_FACTOR,
        "constexpr int PACKED_BANK_FACTOR    = %d;" % PACKED_BANK_FACTOR,
        "",
        "// Parallelism",
        "constexpr int CNU_PARALLEL = %d;" % CNU_PARALLEL,
        "constexpr int VNU_PARALLEL = %d;" % VNU_PARALLEL,
        "constexpr int CONVERGENCE_PARALLEL = %d;" % CONVERGENCE_PARALLEL,
        "",
        "// Message and prior quantization",
        "constexpr int MSG_INT_BITS = %d;" % MSG_INT_BITS,
        "constexpr int MSG_MAX_MAG  = (1 << MSG_INT_BITS) - 1;",
        "constexpr int PRIOR_PACK_FACTOR = %d;" % PRIOR_PACK_FACTOR,
        "constexpr int PRIOR_WORD_BITS   = 6 * PRIOR_PACK_FACTOR;",
        "constexpr float SCALE_S = %.1ff;" % (float(SCALE_S_FIXED) / float(SCALE_ONE_FIXED)),
        "constexpr int SCALE_FRAC_BITS = %d;" % SCALE_FRAC_BITS,
        "constexpr int SCALE_ONE_FIXED = 1 << SCALE_FRAC_BITS;",
        "constexpr int SCALE_S_FIXED   = %d;" % SCALE_S_FIXED,
        "constexpr int POST_EXTRA_BITS = %d;" % POST_EXTRA_BITS,
        "constexpr int POST_MAG_BITS   = MSG_INT_BITS + POST_EXTRA_BITS;",
        "constexpr int POST_TOTAL_BITS = POST_MAG_BITS + 1;",
        "",
        "// Relay-BP LEG and iteration settings",
        "constexpr int MEM_SHIFT = %d;" % MEM_SHIFT,
        "constexpr int MEM_SCALE = 1 << MEM_SHIFT;",
        "constexpr int MAX_LEGS = %d;" % MAX_LEGS,
        "constexpr int GAMMA_NUM[MAX_LEGS] = {1, 3, 5, 7};",
        "constexpr int LEG_BETA[MAX_LEGS]  = {7, 5, 3, 1};",
        "constexpr int ALPHA_SHIFT_MAX = 4;",
        "constexpr int MAX_ITERS_PER_LEG = %d;" % MAX_ITERS_PER_LEG,
        "constexpr int GLOBAL_MAX_ITERS = %d;" % GLOBAL_MAX_ITERS,
        "constexpr int CONVERGENCE_CHECK_INTERVAL = %d;" % CONVERGENCE_CHECK_INTERVAL,
        "constexpr int MAX_SOLUTIONS = %d;" % MAX_SOLUTIONS,
        "constexpr int MAX_TOTAL_ITERS = MAX_LEGS * MAX_ITERS_PER_LEG;",
        "",
        "// Weight accumulation",
        "constexpr int WEIGHT_BITS = %d;" % WEIGHT_BITS,
        "constexpr int WEIGHT_MAX  = (1 << WEIGHT_BITS) - 1;",
        "",
        "// Carry window",
        "constexpr int CARRY_DETECTOR_START = COMMIT_C * M_PER_CYCLE;  // %d" % CARRY_DETECTOR_START,
        "constexpr int CARRY_SIZE           = M_PER_CYCLE;             // %d" % CARRY_SIZE,
        "",
        "// Logical action matrix size",
        "constexpr int A_NUM_NONZEROS = %d;" % A_NUM_NONZEROS,
        "",
        "// Compile-time parameter checks. These keep the generated constants",
        "// aligned with the packed-prior ABI and static bank schedules.",
        "static_assert(NUM_DETECTORS == WINDOW_W * M_PER_CYCLE, \"detector count must match window geometry\");",
        "static_assert(NUM_NONZEROS == NUM_DETECTORS * H_AVG_ROW_DEGREE_EXAMPLE, \"synthetic H edge count mismatch\");",
        "static_assert(NUM_EDGES == NUM_NONZEROS, \"edge count alias mismatch\");",
        "static_assert(H_AVG_ROW_DEGREE_EXAMPLE <= H_MAX_ROW_DEGREE, \"row degree exceeds row storage cap\");",
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


def render_tail():
    return "\n".join([
        "// ================================================================",
        "// Dummy priors",
        "// ================================================================",
        "constexpr int PRIOR_INIT[NUM_FAULTS] = {};",
        "",
        "// ================================================================",
        "// Dummy A~ logical action matrix",
        "// ================================================================",
        "constexpr int A_ROW_DEGREES[K_OBSERVABLES] = {};",
        "constexpr int A_ROW_NEIGHBORS[K_OBSERVABLES][A_MAX_ROW_DEGREE] = {};",
        "constexpr int A_CSR_ROW_PTR[K_OBSERVABLES + 1] = {};",
        "constexpr int A_CSR_COL_IDX[A_NUM_NONZEROS] = {};",
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


def render_constants(config, matrix):
    apply_config(config)
    return render_preamble() + "\n" + render_generated_section(matrix) + "\n" + render_tail()


def render_generated_section(matrix):
    row_edges = matrix.edges_by_row
    col_edges = matrix.edges_by_col
    active_faults = build_active_faults(matrix)

    edge_for_check = [_pad([edge.edge_idx for edge in row], H_MAX_ROW_DEGREE) for row in row_edges]
    edge_for_var = [_pad([edge.edge_idx for edge in col], H_MAX_COL_DEGREE) for col in col_edges]

    bank_for_check = [_pad([edge.bank for edge in row], H_MAX_ROW_DEGREE) for row in row_edges]
    addr_for_check = [_pad([edge.addr for edge in row], H_MAX_ROW_DEGREE) for row in row_edges]
    bank_for_var = [_pad([edge.bank for edge in col], H_MAX_COL_DEGREE) for col in col_edges]
    addr_for_var = [_pad([edge.addr for edge in col], H_MAX_COL_DEGREE) for col in col_edges]

    row_neighbors = [_pad([edge.var_idx for edge in row], H_MAX_ROW_DEGREE) for row in row_edges]
    col_neighbors = [_pad([edge.check_idx for edge in col], H_MAX_COL_DEGREE) for col in col_edges]
    cnu_schedule = build_bank_major_schedule(
        matrix.num_detectors, CNU_PARALLEL, matrix.edges_by_row)
    cnu_lane_slot_schedule = build_lane_slot_schedule(
        matrix.num_detectors, CNU_PARALLEL, H_MAX_ROW_DEGREE, matrix.edges_by_row)
    vnu_schedule = build_bank_major_schedule(
        matrix.num_faults, VNU_PARALLEL, matrix.edges_by_col,
        NUM_FAULT_WORDS * (PACK_BITS // VNU_PARALLEL))
    vnu_lane_slot_schedule = build_lane_slot_schedule(
        matrix.num_faults, VNU_PARALLEL, H_MAX_COL_DEGREE, matrix.edges_by_col,
        NUM_FAULT_WORDS * (PACK_BITS // VNU_PARALLEL))
    detector_schedule = build_detector_schedule(matrix)

    def schedule_values(schedule, field):
        values = []
        for group in schedule:
            group_values = []
            for ports in group:
                port_values = []
                for entry in ports:
                    if field == "valid":
                        value = int(entry.valid)
                    elif field == "addr":
                        value = entry.edge.addr if entry.valid else 0
                    else:
                        value = getattr(entry, field) if entry.valid else 0
                    port_values.append(value)
                group_values.append(port_values)
            values.append(group_values)
        return values

    def lane_slot_values(schedule, field):
        values = []
        for group in schedule:
            group_values = []
            for lane_entries in group:
                slot_values = []
                for entry in lane_entries:
                    if field == "valid":
                        value = int(entry.valid)
                    elif field == "bank":
                        value = entry.edge.bank if entry.valid else 0
                    elif field == "addr":
                        value = entry.edge.addr if entry.valid else 0
                    else:
                        value = getattr(entry, field) if entry.valid else 0
                    slot_values.append(value)
                group_values.append(slot_values)
            values.append(group_values)
        return values

    def detector_schedule_values(field):
        values = []
        for group in detector_schedule:
            group_values = []
            for ports in group:
                port_values = []
                for entry in ports:
                    if field == "valid":
                        value = int(entry.valid)
                    elif field == "addr":
                        value = entry.edge.var_idx // PACKED_BANK_FACTOR if entry.valid else 0
                    else:
                        value = getattr(entry, field) if entry.valid else 0
                    port_values.append(value)
                group_values.append(port_values)
            values.append(group_values)
        return values

    csr_row_ptr = [0]
    csr_col_idx = []
    for row in row_edges:
        csr_col_idx.extend(edge.var_idx for edge in row)
        csr_row_ptr.append(len(csr_col_idx))

    parts = [
        "// ================================================================",
        "// Synthetic generated H~ arrays",
        "// Deterministic fake sparse matrix for HLS resource/performance testing.",
        "// Rows have degree %d; columns are capped at H_MAX_COL_DEGREE." % ROW_DEGREE,
        "// Regenerate with tools/generate_fake_h_constants.py.",
        "// ================================================================",
        "",
        "constexpr int NUM_ACTIVE_FAULTS = %d;" % len(active_faults),
        "",
        _format_flat_array("ACTIVE_FAULT_INDEX", "NUM_ACTIVE_FAULTS", active_faults),
        "",
        _format_flat_array("H_ROW_DEGREES", "NUM_DETECTORS", matrix.row_degrees),
        "",
        _format_flat_array("H_COL_DEGREES", "NUM_FAULTS", matrix.col_degrees),
        "",
        _format_2d_array("EDGE_FOR_CHECK_POS", "NUM_DETECTORS][H_MAX_ROW_DEGREE", edge_for_check),
        "",
        _format_2d_array("EDGE_FOR_VAR_POS", "NUM_FAULTS][H_MAX_COL_DEGREE", edge_for_var),
        "",
        _format_2d_array("EDGE_BANK_FOR_CHECK_POS", "NUM_DETECTORS][H_MAX_ROW_DEGREE", bank_for_check),
        "",
        _format_2d_array("EDGE_ADDR_FOR_CHECK_POS", "NUM_DETECTORS][H_MAX_ROW_DEGREE", addr_for_check),
        "",
        _format_2d_array("EDGE_BANK_FOR_VAR_POS", "NUM_FAULTS][H_MAX_COL_DEGREE", bank_for_var),
        "",
        _format_2d_array("EDGE_ADDR_FOR_VAR_POS", "NUM_FAULTS][H_MAX_COL_DEGREE", addr_for_var),
        "",
        "constexpr int CNU_EDGE_GROUPS = (NUM_DETECTORS + CNU_PARALLEL - 1) / CNU_PARALLEL;",
        "constexpr int VNU_EDGE_GROUPS = NUM_FAULT_WORDS * (PACK_BITS / VNU_PARALLEL);",
        "constexpr int DET_EDGE_GROUPS = (NUM_DETECTORS + CONVERGENCE_PARALLEL - 1) / CONVERGENCE_PARALLEL;",
        "constexpr int EDGE_BANK_PORTS = %d;" % BANK_PORTS,
        "constexpr int DET_BANK_PORTS = %d;" % BANK_PORTS,
        "static_assert(EDGE_BANK_PORTS == 2, \"message banks require dual-port scheduling\");",
        "static_assert(DET_BANK_PORTS == 2, \"detector banks require dual-port scheduling\");",
        "static_assert((PACK_BITS % VNU_PARALLEL) == 0, \"VNU groups must divide packed words\");",
        "static_assert(NUM_ACTIVE_FAULTS > 0, \"generated H must contain active faults\");",
        "static_assert(NUM_ACTIVE_FAULTS <= NUM_FAULTS, \"active fault table exceeds NUM_FAULTS\");",
        "static_assert(CNU_EDGE_GROUPS == (NUM_DETECTORS + CNU_PARALLEL - 1) / CNU_PARALLEL, \"CNU schedule group mismatch\");",
        "static_assert(VNU_EDGE_GROUPS == NUM_FAULT_WORDS * (PACK_BITS / VNU_PARALLEL), \"VNU schedule group mismatch\");",
        "static_assert(DET_EDGE_GROUPS == (NUM_DETECTORS + CONVERGENCE_PARALLEL - 1) / CONVERGENCE_PARALLEL, \"detector schedule group mismatch\");",
        "",
        _format_3d_array(
            "CNU_EDGE_VALID", "CNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS",
            schedule_values(cnu_schedule, "valid")),
        "",
        _format_3d_array(
            "CNU_EDGE_LANE", "CNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS",
            schedule_values(cnu_schedule, "lane")),
        "",
        _format_3d_array(
            "CNU_EDGE_SLOT", "CNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS",
            schedule_values(cnu_schedule, "slot")),
        "",
        _format_3d_array(
            "CNU_EDGE_ADDR", "CNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS",
            schedule_values(cnu_schedule, "addr")),
        "",
        _format_3d_array(
            "CNU_LANE_EDGE_VALID", "CNU_EDGE_GROUPS][CNU_PARALLEL][H_MAX_ROW_DEGREE",
            lane_slot_values(cnu_lane_slot_schedule, "valid")),
        "",
        _format_3d_array(
            "CNU_LANE_EDGE_BANK", "CNU_EDGE_GROUPS][CNU_PARALLEL][H_MAX_ROW_DEGREE",
            lane_slot_values(cnu_lane_slot_schedule, "bank")),
        "",
        _format_3d_array(
            "CNU_LANE_EDGE_ADDR", "CNU_EDGE_GROUPS][CNU_PARALLEL][H_MAX_ROW_DEGREE",
            lane_slot_values(cnu_lane_slot_schedule, "addr")),
        "",
        _format_3d_array(
            "VNU_EDGE_VALID", "VNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS",
            schedule_values(vnu_schedule, "valid")),
        "",
        _format_3d_array(
            "VNU_EDGE_LANE", "VNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS",
            schedule_values(vnu_schedule, "lane")),
        "",
        _format_3d_array(
            "VNU_EDGE_SLOT", "VNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS",
            schedule_values(vnu_schedule, "slot")),
        "",
        _format_3d_array(
            "VNU_EDGE_ADDR", "VNU_EDGE_GROUPS][EDGE_BANK_FACTOR][EDGE_BANK_PORTS",
            schedule_values(vnu_schedule, "addr")),
        "",
        _format_3d_array(
            "VNU_LANE_EDGE_VALID", "VNU_EDGE_GROUPS][VNU_PARALLEL][H_MAX_COL_DEGREE",
            lane_slot_values(vnu_lane_slot_schedule, "valid")),
        "",
        _format_3d_array(
            "VNU_LANE_EDGE_BANK", "VNU_EDGE_GROUPS][VNU_PARALLEL][H_MAX_COL_DEGREE",
            lane_slot_values(vnu_lane_slot_schedule, "bank")),
        "",
        _format_3d_array(
            "VNU_LANE_EDGE_ADDR", "VNU_EDGE_GROUPS][VNU_PARALLEL][H_MAX_COL_DEGREE",
            lane_slot_values(vnu_lane_slot_schedule, "addr")),
        "",
        _format_3d_array(
            "DET_EDGE_VALID", "DET_EDGE_GROUPS][PACKED_BANK_FACTOR][DET_BANK_PORTS",
            detector_schedule_values("valid")),
        "",
        _format_3d_array(
            "DET_EDGE_LANE", "DET_EDGE_GROUPS][PACKED_BANK_FACTOR][DET_BANK_PORTS",
            detector_schedule_values("lane")),
        "",
        _format_3d_array(
            "DET_EDGE_ADDR", "DET_EDGE_GROUPS][PACKED_BANK_FACTOR][DET_BANK_PORTS",
            detector_schedule_values("addr")),
        "",
        _format_2d_array("H_ROW_NEIGHBORS", "NUM_DETECTORS][H_MAX_ROW_DEGREE", row_neighbors),
        "",
        _format_2d_array("H_COL_NEIGHBORS", "NUM_FAULTS][H_MAX_COL_DEGREE", col_neighbors),
        "",
        "// CSR form of H~",
        _format_flat_array("H_CSR_ROW_PTR", "NUM_DETECTORS + 1", csr_row_ptr),
        "",
        _format_flat_array("H_CSR_COL_IDX", "NUM_NONZEROS", csr_col_idx),
    ]
    return "\n".join(parts) + "\n"


def rewrite_constants(path=CONSTANTS, config=None):
    cfg = apply_config(config or DEFAULT_CONFIG)
    matrix = build_fake_h()
    Path(path).write_text(render_constants(cfg, matrix))
    return matrix


def _load_or_default_config(path):
    path = Path(path)
    if path.exists():
        return load_config(path)
    return normalize_config(DEFAULT_CONFIG)


def _print_summary(path, matrix):
    active_cols = sum(1 for degree in matrix.col_degrees if degree > 0)
    checks = check_bank_conflicts(matrix)
    bank_depth = max(edge.addr for row in matrix.edges_by_row for edge in row) + 1
    print("constants=%s" % path)
    print("edges=%d active_columns=%d max_col_degree=%d bank_depth=%d" %
          (matrix.num_edges, active_cols, max(matrix.col_degrees), bank_depth))
    print("cnu_max_bank_accesses=%d vnu_max_bank_accesses=%d" %
          (checks["cnu_max_bank_accesses"], checks["vnu_max_bank_accesses"]))
    print("detector_max_bank_accesses=%d" %
          checks["detector_max_bank_accesses"])


def main():
    parser = argparse.ArgumentParser(
        description="Generate the full Relay-BP constants.h from validated parameters.")
    parser.add_argument(
        "--interactive", action="store_true",
        help="prompt for required parameters, show restrictions, and save the config")
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH),
        help="JSON config path (default: configs/constants_config.json)")
    parser.add_argument(
        "--output", default=str(CONSTANTS),
        help="constants.h output path (default: src/constants.h)")
    parser.add_argument(
        "--check", action="store_true",
        help="validate config and generated schedules without writing constants.h")
    parser.add_argument(
        "--write-config", action="store_true",
        help="write the resolved JSON config, useful for recording project defaults")
    args = parser.parse_args()

    cfg = _load_or_default_config(args.config)
    if args.interactive:
        cfg = prompt_config(cfg)
        write_config(cfg, args.config)
        print("wrote config %s" % args.config)

    cfg = apply_config(cfg)
    if args.write_config and not args.interactive:
        write_config(cfg, args.config)
        print("wrote config %s" % args.config)
    matrix = build_fake_h()
    if not args.check:
        Path(args.output).write_text(render_constants(cfg, matrix))
        print("wrote %s" % args.output)
    else:
        print("check passed; no constants.h written")
    _print_summary(args.output, matrix)


if __name__ == "__main__":
    main()
