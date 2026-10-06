#!/usr/bin/env python3
"""Protect existing constants while removing unused reference representations."""
import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNUSED_CONSTANTS = (
    "EDGE_BANK_FOR_CHECK_POS", "EDGE_ADDR_FOR_CHECK_POS",
    "EDGE_BANK_FOR_VAR_POS", "EDGE_ADDR_FOR_VAR_POS",
    "H_COL_NEIGHBORS", "H_CSR_ROW_PTR", "H_CSR_COL_IDX",
    "PRIOR_INIT", "PRIOR_LAMBDA", "A_CSR_ROW_PTR", "A_CSR_COL_IDX",
    "CONVERGENCE_MASK", "CARRY_OUT_ROWS",
)
# Committed headers and renderers already differ. Lock each independently so
# this cleanup cannot silently replace prior packing, FIFO or schedule settings.
BASELINE_SIGNATURES = {
    "RelayBP_pack64_c8_v16": (
        "0f04dbcfa46feb7b68240eb1e7bf501c259c4250c48af28950e4a32bd070b4a9",
        "8e731cecb12f39f13295649d1b0b027d68aeb8f4023e8459e849bf69890e81d1"),
    "RelayBP_pack64_c16_v16": (
        "4156fbf506dd91fab267672a57e9e126de602280a20411f88405bd29c53c425f",
        "57ad514d643dacc7db118e7274df1d2abd261f27ba55bb384eab56aff857614a"),
    "RelayBP_pack64_c16_v32": (
        "7e5cce5336c226079bd73c5bd0702969e1e941fba5d389c214a2b0306d677b80",
        "184cb9afa81c36665d30ea1a04d5017d013f261c2be39e535bf29fbebbe62488"),
}


def retained_signature(text):
    declarations = {
        match[1]: re.sub(r"\s+", "", match[0])
        for match in re.finditer(
            r"constexpr\s+(?:int|float)\s+(\w+)[^;]*;", text)
        if match[1] not in UNUSED_CONSTANTS
    }
    return hashlib.sha256(json.dumps(declarations, sort_keys=True).encode()).hexdigest()


class ConstantsCleanupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "cleanup_fake", ROOT / "tools/generate_fake_h_constants.py")
        cls.fake = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.fake)
        matrix = cls.fake.build_fake_h()
        cls.generated = cls.fake.render_constants(cls.fake.DEFAULT_CONFIG, matrix)
        cls.committed = (ROOT / "src/constants.h").read_text()

    def assert_unused_absent(self, text):
        for name in UNUSED_CONSTANTS:
            with self.subTest(name=name):
                self.assertIsNone(re.search(r"\b" + name + r"\b", text), name)

    def test_committed_header_omits_unused_arrays(self):
        self.assert_unused_absent(self.committed)

    def test_fake_renderer_omits_unused_arrays(self):
        self.assert_unused_absent(self.generated)

    def test_committed_retained_constants_are_unchanged(self):
        self.assertEqual(retained_signature(self.committed),
                         BASELINE_SIGNATURES[ROOT.name][0])

    def test_fake_renderer_retained_constants_are_unchanged(self):
        self.assertEqual(retained_signature(self.generated),
                         BASELINE_SIGNATURES[ROOT.name][1])

    def test_real_renderer_omits_unused_arrays(self):
        spec = importlib.util.spec_from_file_location(
            "cleanup_real", ROOT / "tools/generate_real_circuit_constants.py")
        real = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(real)
        config = dict(real.fake.DEFAULT_CONFIG)
        config.update({
            "WINDOW_W": 2, "M_PER_CYCLE": 4, "NUM_FAULTS": 4,
            "CNU_PARALLEL": 2, "VNU_PARALLEL": 2,
            "CONVERGENCE_PARALLEL": 2, "PACK_BITS": 4,
            "PACKED_BANK_FACTOR": 4, "PRIOR_PACK_FACTOR": 4,
            "PRIOR_BANK_FACTOR": 4, "EDGE_BANK_FACTOR": 4,
        })
        graph = real.CircuitGraph(
            num_detectors=4, num_faults=4,
            edges=[(0, 0), (0, 1), (2, 3)],
            logical_edges=[(0, 1)], priors=[0.1, 0.2, 0.3, 0.4])
        matrix = real.build_real_h(graph, config)
        self.assert_unused_absent(real.render_real_constants(config, graph, matrix))


if __name__ == "__main__":
    unittest.main()
