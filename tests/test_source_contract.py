"""Check RelayHLS control settings, generator ABI and retained graph tables."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = sorted((ROOT / "variants").glob("RelayBP_pack64_*"))
UNUSED = (
    "EDGE_BANK_FOR_CHECK_POS", "EDGE_ADDR_FOR_CHECK_POS",
    "EDGE_BANK_FOR_VAR_POS", "EDGE_ADDR_FOR_VAR_POS", "H_COL_NEIGHBORS",
    "H_CSR_ROW_PTR", "H_CSR_COL_IDX", "PRIOR_INIT", "PRIOR_LAMBDA",
    "A_CSR_ROW_PTR", "A_CSR_COL_IDX", "CONVERGENCE_MASK", "CARRY_OUT_ROWS",
    "CNU_LANE_EDGE_VALID", "CNU_LANE_EDGE_BANK", "CNU_LANE_EDGE_ADDR",
    "VNU_LANE_EDGE_VALID", "VNU_LANE_EDGE_BANK", "VNU_LANE_EDGE_ADDR",
)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arrays(text):
    text = re.sub(r"//[^\n]*", "", text)
    return {m[1]: re.sub(r"\s+", "", m[0]) for m in re.finditer(
        r"constexpr\s+int\s+(\w+)\[[^;]*;", text)}


class SourceContract(unittest.TestCase):
    def test_fixed_leg_schedule_rejects_inconsistent_parameters(self):
        for variant in VARIANTS:
            fake = load(variant / "tools/generate_fake_h_constants.py", "source_parameters")
            for key, value in (("MAX_LEGS", 5), ("MAX_LEGS", 3), ("MEM_SHIFT", 2)):
                with self.subTest(variant=variant.name, parameter=key, value=value):
                    config = dict(fake.DEFAULT_CONFIG)
                    config[key] = value
                    with self.assertRaises(ValueError):
                        fake.validate_config(config)

    def test_controller_and_datapath(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant.name):
                controller = (variant / "src/relay_bp.h").read_text()
                self.assertIn("is_initial_leg && (t == 0)", controller)
                self.assertIn("MEM_SHIFT, leg_iters, r == 0, iters_this_leg", controller)
                self.assertIn("return compute_weight_parallel(hard_decisions, priors)", controller)
                self.assertIn("VNU_GROUPS:", (variant / "src/bp_iteration.h").read_text())
                self.assertIn("PUBLISH_CORRECTION:", (variant / "src/decoder_top.cpp").read_text())

    def test_generator_matches_committed_arrays_and_abi(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant.name):
                fake = load(variant / "tools/generate_fake_h_constants.py", "source_fake")
                config = json.loads((variant / "configs/constants_config.json").read_text())
                self.assertEqual(config["GLOBAL_MAX_ITERS"], 40)
                fake.apply_config(config)
                generated = fake.render_constants(config, fake.build_fake_h())
                committed = (variant / "src/constants.h").read_text()
                self.assertEqual(arrays(generated), arrays(committed))
                for text in (generated, committed):
                    self.assertRegex(text, r"PRIOR_WORD_BITS\s*=\s*PRIOR_PACK_FACTOR\s*\*\s*MSG_INT_BITS")
                    self.assertIn("constexpr int NUM_PRIOR_WORDS", text)
                    self.assertIn("constexpr int FIFO_DEPTH = WINDOW_W + COMMIT_C;", text)
                    self.assertIn("constexpr int GLOBAL_MAX_ITERS = 40;", text)
                    for name in UNUSED:
                        self.assertNotRegex(text, r"\b" + name + r"\b")

    def test_real_generator_uses_same_packed_prior_abi(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant.name):
                real = load(variant / "tools/generate_real_circuit_constants.py", "source_real")
                config = dict(real.fake.DEFAULT_CONFIG)
                config.update(WINDOW_W=2, M_PER_CYCLE=2, NUM_FAULTS=5,
                              CNU_PARALLEL=2, VNU_PARALLEL=2,
                              CONVERGENCE_PARALLEL=2, PACK_BITS=4,
                              PACKED_BANK_FACTOR=4, PRIOR_PACK_FACTOR=4,
                              PRIOR_BANK_FACTOR=4, EDGE_BANK_FACTOR=4)
                graph = real.CircuitGraph(4, 5, [(0, 0), (0, 1), (1, 1),
                                               (2, 2), (3, 3)], [(0, 1)], [])
                matrix = real.build_real_h(graph, config)
                text = real.render_real_constants(config, graph, matrix)
                self.assertRegex(text, r"PRIOR_WORD_BITS\s*=\s*PRIOR_PACK_FACTOR\s*\*\s*MSG_INT_BITS")
                self.assertIn("constexpr int NUM_PRIOR_WORDS", text)
                self.assertIn("constexpr int FIFO_DEPTH = WINDOW_W + COMMIT_C;", text)
                for name in UNUSED:
                    self.assertNotRegex(text, r"\b" + name + r"\b")


if __name__ == "__main__":
    unittest.main()
