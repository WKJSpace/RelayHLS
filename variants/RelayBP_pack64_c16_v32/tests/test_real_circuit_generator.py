#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_real_circuit_constants.py"
FAKE_GENERATOR = ROOT / "tools" / "generate_fake_h_constants.py"


class RealCircuitGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("generate_real_circuit_constants", GENERATOR)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

        fake_spec = importlib.util.spec_from_file_location("generate_fake_h_constants", FAKE_GENERATOR)
        cls.fake = importlib.util.module_from_spec(fake_spec)
        fake_spec.loader.exec_module(cls.fake)

    def test_parse_csv_edges_with_header(self):
        text = "detector,fault\n0,0\n0,1\n2,1\n"
        graph = self.mod.parse_csv_text(text)
        self.assertEqual(graph.num_detectors, 3)
        self.assertEqual(graph.num_faults, 2)
        self.assertEqual(sorted(graph.edges), [(0, 0), (0, 1), (2, 1)])

    def test_parse_flat_stim_dem_errors_and_logicals(self):
        text = """
        error(0.001) D0 D2 L1
        error(0.125) D1
        """
        graph = self.mod.parse_dem_text(text)
        self.assertEqual(graph.num_detectors, 3)
        self.assertEqual(graph.num_faults, 2)
        self.assertEqual(sorted(graph.edges), [(0, 0), (1, 1), (2, 0)])
        self.assertEqual(graph.logical_edges, [(1, 0)])
        self.assertEqual(graph.priors, [0.001, 0.125])

    def test_parse_json_edges_and_logicals(self):
        text = '{"num_detectors": 4, "num_faults": 3, "edges": [[0, 0], [3, 2]], "logical_edges": [[1, 2]]}'
        graph = self.mod.parse_json_text(text)
        self.assertEqual(graph.num_detectors, 4)
        self.assertEqual(graph.num_faults, 3)
        self.assertEqual(graph.edges, [(0, 0), (3, 2)])
        self.assertEqual(graph.logical_edges, [(1, 2)])

    def test_real_matrix_renders_actual_nonzero_count(self):
        cfg = dict(self.fake.DEFAULT_CONFIG)
        cfg.update({
            "WINDOW_W": 2,
            "M_PER_CYCLE": 4,
            "NUM_FAULTS": 4,
            "CNU_PARALLEL": 2,
            "VNU_PARALLEL": 2,
            "CONVERGENCE_PARALLEL": 2,
            "PACK_BITS": 4,
            "PACKED_BANK_FACTOR": 4,
            "PRIOR_PACK_FACTOR": 4,
            "PRIOR_BANK_FACTOR": 4,
            "EDGE_BANK_FACTOR": 4,
        })
        graph = self.mod.CircuitGraph(
            num_detectors=4,
            num_faults=4,
            edges=[(0, 0), (0, 1), (2, 3)],
            logical_edges=[(0, 1)],
            priors=[0.1, 0.2, 0.3, 0.4],
        )
        matrix = self.mod.build_real_h(graph, cfg)
        text = self.mod.render_real_constants(cfg, graph, matrix)
        self.assertIn("constexpr int NUM_NONZEROS = 3;", text)
        self.assertEqual(self.mod.fake.EDGE_BANK_DEPTH, 1)
        self.assertIn("constexpr int A_NUM_NONZEROS = 1;", text)
        self.assertIn("constexpr int A_ROW_DEGREES[K_OBSERVABLES]", text)
        self.assertIn("constexpr int NUM_ACTIVE_FAULTS = 3;", text)
        self.assertTrue(text.rstrip().endswith("#endif  // CONSTANTS_H"))

    def test_rejects_row_degree_over_storage_cap(self):
        cfg = dict(self.fake.DEFAULT_CONFIG)
        cfg.update({
            "WINDOW_W": 2,
            "M_PER_CYCLE": 1,
            "NUM_FAULTS": 3,
            "ROW_DEGREE": 2,
            "H_MAX_ROW_DEGREE": 2,
        })
        graph = self.mod.CircuitGraph(1, 3, [(0, 0), (0, 1), (0, 2)], [], [])
        with self.assertRaises(ValueError) as ctx:
            self.mod.build_real_h(graph, cfg)
        self.assertIn("row degree", str(ctx.exception))

    def test_rejects_unfixable_detector_bank_conflict(self):
        cfg = dict(self.fake.DEFAULT_CONFIG)
        cfg.update({
            "WINDOW_W": 2,
            "M_PER_CYCLE": 4,
            "NUM_FAULTS": 130,
            "CONVERGENCE_PARALLEL": 4,
        })
        graph = self.mod.CircuitGraph(4, 130, [(0, 0), (1, 64), (2, 128)], [], [])
        with self.assertRaises(ValueError) as ctx:
            self.mod.build_real_h(graph, cfg)
        self.assertIn("detector bank conflict", str(ctx.exception))

    def test_cli_writes_temp_constants(self):
        cfg = dict(self.fake.DEFAULT_CONFIG)
        cfg.update({
            "WINDOW_W": 2,
            "M_PER_CYCLE": 4,
            "NUM_FAULTS": 4,
            "CNU_PARALLEL": 2,
            "VNU_PARALLEL": 2,
            "CONVERGENCE_PARALLEL": 2,
            "PACK_BITS": 4,
            "PACKED_BANK_FACTOR": 4,
            "PRIOR_PACK_FACTOR": 4,
            "PRIOR_BANK_FACTOR": 4,
            "EDGE_BANK_FACTOR": 4,
        })
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = Path(tmpdir) / "graph.csv"
            config_path = Path(tmpdir) / "config.json"
            output_path = Path(tmpdir) / "constants.h"
            graph_path.write_text("detector,fault\n0,0\n0,1\n2,3\n")
            self.fake.write_config(cfg, config_path)
            self.mod.main([
                "--input", str(graph_path),
                "--format", "csv",
                "--config", str(config_path),
                "--output", str(output_path),
            ])
            self.assertIn("constexpr int NUM_NONZEROS = 3;", output_path.read_text())


if __name__ == "__main__":
    unittest.main()
