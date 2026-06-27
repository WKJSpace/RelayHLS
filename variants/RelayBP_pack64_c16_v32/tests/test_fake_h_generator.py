#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_fake_h_constants.py"

class FakeHGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("generate_fake_h_constants", GENERATOR)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def test_generated_matrix_has_real_edges_and_valid_bounds(self):
        matrix = self.mod.build_fake_h()
        self.assertEqual(matrix.num_detectors, 1008)
        self.assertEqual(matrix.num_faults, 9000)
        self.assertEqual(matrix.num_edges, 8064)
        self.assertTrue(all(deg == 8 for deg in matrix.row_degrees))
        self.assertGreater(sum(1 for deg in matrix.col_degrees if deg > 0), 6000)
        self.assertLessEqual(max(matrix.col_degrees), 8)
        self.assertEqual(len(matrix.edges_by_row), matrix.num_detectors)
        self.assertEqual(len(matrix.edges_by_col), matrix.num_faults)
        self.assertTrue(all(len(row) == 8 for row in matrix.edges_by_row))
        self.assertTrue(all(len(col) <= 8 for col in matrix.edges_by_col))

    def test_generated_bank_assignment_respects_dual_port_limits(self):
        matrix = self.mod.build_fake_h()
        stats = self.mod.check_bank_conflicts(matrix)
        self.assertLessEqual(stats["cnu_max_bank_accesses"], self.mod.BANK_PORTS)
        self.assertLessEqual(stats["vnu_max_bank_accesses"], self.mod.BANK_PORTS)
        self.assertLessEqual(stats["detector_max_bank_accesses"], self.mod.BANK_PORTS)
        max_addr = max(edge.addr for row in matrix.edges_by_row for edge in row)
        self.assertLess(max_addr, self.mod.EDGE_BANK_DEPTH)

    def test_variant_uses_global_ten_iteration_budget(self):
        self.assertEqual(self.mod.MAX_ITERS_PER_LEG, 10)
        self.assertEqual(self.mod.GLOBAL_MAX_ITERS, 10)
        self.assertEqual(self.mod.CONVERGENCE_CHECK_INTERVAL, 2)
        self.assertEqual(self.mod.CNU_PARALLEL, self.mod.DEFAULT_CONFIG["CNU_PARALLEL"])
        self.assertEqual(self.mod.VNU_PARALLEL, self.mod.DEFAULT_CONFIG["VNU_PARALLEL"])

    def test_bank_major_schedules_cover_every_edge_once(self):
        matrix = self.mod.build_fake_h()
        cnu_schedule = self.mod.build_bank_major_schedule(
            matrix.num_detectors, self.mod.CNU_PARALLEL, matrix.edges_by_row)
        vnu_schedule = self.mod.build_bank_major_schedule(
            matrix.num_faults, self.mod.VNU_PARALLEL, matrix.edges_by_col,
            self.mod.NUM_FAULT_WORDS * (self.mod.PACK_BITS // self.mod.VNU_PARALLEL))

        for schedule in (cnu_schedule, vnu_schedule):
            scheduled_edges = []
            for group in schedule:
                self.assertEqual(len(group), self.mod.EDGE_BANK_FACTOR)
                for ports in group:
                    self.assertEqual(len(ports), self.mod.BANK_PORTS)
                    scheduled_edges.extend(
                        entry.edge.edge_idx for entry in ports if entry.valid)
            self.assertEqual(len(scheduled_edges), matrix.num_edges)
            self.assertEqual(sorted(scheduled_edges), list(range(matrix.num_edges)))

    def test_vnu_schedule_covers_packed_word_tail(self):
        matrix = self.mod.build_fake_h()
        hardware_group_count = (
            self.mod.NUM_FAULT_WORDS *
            (self.mod.PACK_BITS // self.mod.VNU_PARALLEL))
        schedule = self.mod.build_bank_major_schedule(
            matrix.num_faults, self.mod.VNU_PARALLEL, matrix.edges_by_col,
            hardware_group_count)
        self.assertEqual(len(schedule), hardware_group_count)
        last_real_group = (matrix.num_faults - 1) // self.mod.VNU_PARALLEL
        self.assertTrue(any(entry.valid for bank in schedule[last_real_group] for entry in bank))
        for group in range(last_real_group + 1, hardware_group_count):
            self.assertFalse(any(entry.valid for bank in schedule[group] for entry in bank))

    def test_rendered_constants_expose_static_bank_schedules(self):
        generated = self.mod.render_generated_section(self.mod.build_fake_h())
        for name in (
                "NUM_ACTIVE_FAULTS", "ACTIVE_FAULT_INDEX",
                "CNU_EDGE_VALID", "CNU_EDGE_LANE", "CNU_EDGE_SLOT", "CNU_EDGE_ADDR",
                "VNU_EDGE_VALID", "VNU_EDGE_LANE", "VNU_EDGE_SLOT", "VNU_EDGE_ADDR",
                "DET_EDGE_VALID", "DET_EDGE_LANE", "DET_EDGE_ADDR"):
            self.assertIn(name, generated)

    def test_full_constants_renderer_emits_guard_and_static_checks(self):
        matrix = self.mod.build_fake_h()
        text = self.mod.render_constants(self.mod.DEFAULT_CONFIG, matrix)
        self.assertIn("#ifndef CONSTANTS_H", text)
        self.assertIn("constexpr int CNU_PARALLEL = %d;" % self.mod.CNU_PARALLEL, text)
        self.assertIn("constexpr int VNU_PARALLEL = %d;" % self.mod.VNU_PARALLEL, text)
        self.assertIn("static_assert(PACKED_BANK_FACTOR == PACK_BITS", text)
        self.assertIn("static_assert(PRIOR_PACK_FACTOR == PACK_BITS", text)
        self.assertIn("static_assert(NUM_ACTIVE_FAULTS > 0", text)
        self.assertIn("constexpr int PRIOR_INIT[NUM_FAULTS] = {};", text)
        self.assertTrue(text.rstrip().endswith("#endif  // CONSTANTS_H"))

    def test_rewrite_constants_can_target_temp_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "constants.h"
            matrix = self.mod.rewrite_constants(output, self.mod.DEFAULT_CONFIG)
            text = output.read_text()
            self.assertEqual(matrix.num_edges, self.mod.NUM_EDGES)
            self.assertIn("Generated by tools/generate_fake_h_constants.py", text)
            self.assertIn("constexpr int NUM_ACTIVE_FAULTS", text)

    def test_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "constants_config.json"
            self.mod.write_config(self.mod.DEFAULT_CONFIG, path)
            loaded = self.mod.load_config(path)
            self.assertEqual(loaded["CNU_PARALLEL"], self.mod.DEFAULT_CONFIG["CNU_PARALLEL"])
            self.assertEqual(loaded["VNU_PARALLEL"], self.mod.DEFAULT_CONFIG["VNU_PARALLEL"])
            self.mod.validate_config(loaded)

    def test_validation_rejects_invalid_parallelism(self):
        bad = dict(self.mod.DEFAULT_CONFIG)
        bad["VNU_PARALLEL"] = 24
        with self.assertRaises(ValueError) as ctx:
            self.mod.validate_config(bad)
        self.assertIn("VNU_PARALLEL must divide PACK_BITS", str(ctx.exception))

    def test_validation_rejects_noncanonical_banking(self):
        bad = dict(self.mod.DEFAULT_CONFIG)
        bad["PACKED_BANK_FACTOR"] = 32
        with self.assertRaises(ValueError) as ctx:
            self.mod.validate_config(bad)
        self.assertIn("PACKED_BANK_FACTOR must equal PACK_BITS", str(ctx.exception))

    def test_active_fault_list_contains_only_nonzero_columns(self):
        matrix = self.mod.build_fake_h()
        active_faults = self.mod.build_active_faults(matrix)
        self.assertEqual(len(active_faults), sum(1 for degree in matrix.col_degrees if degree > 0))
        self.assertGreater(len(active_faults), 6000)
        self.assertLess(len(active_faults), matrix.num_faults)
        self.assertTrue(all(matrix.col_degrees[j] > 0 for j in active_faults))
        self.assertEqual(active_faults, sorted(active_faults))

    def test_prior_bank_mapping_covers_every_fault_once(self):
        mapping = self.mod.build_prior_bank_map()
        self.assertEqual(len(mapping), self.mod.NUM_FAULTS)
        seen = set()
        for fault, bank_addr in enumerate(mapping):
            bank, addr = bank_addr
            self.assertEqual(bank, fault % self.mod.PRIOR_BANK_FACTOR)
            self.assertEqual(addr, fault // self.mod.PRIOR_BANK_FACTOR)
            self.assertLess(bank, self.mod.PRIOR_BANK_FACTOR)
            self.assertLess(addr, self.mod.PRIOR_BANK_DEPTH)
            self.assertNotIn((bank, addr), seen)
            seen.add((bank, addr))

    def test_detector_schedule_covers_every_row_edge_once(self):
        matrix = self.mod.build_fake_h()
        schedule = self.mod.build_detector_schedule(matrix)
        scheduled = []
        for group in schedule:
            self.assertEqual(len(group), self.mod.PACKED_BANK_FACTOR)
            for ports in group:
                self.assertEqual(len(ports), self.mod.BANK_PORTS)
                scheduled.extend(entry.edge.edge_idx for entry in ports if entry.valid)
        self.assertEqual(len(scheduled), matrix.num_edges)
        self.assertEqual(sorted(scheduled), list(range(matrix.num_edges)))

    def test_edge_tables_are_consistent_from_rows_to_columns(self):
        matrix = self.mod.build_fake_h()
        seen = set()
        for check_idx, row in enumerate(matrix.edges_by_row):
            for edge in row:
                self.assertEqual(edge.check_idx, check_idx)
                self.assertIn(edge, matrix.edges_by_col[edge.var_idx])
                self.assertNotIn(edge.edge_idx, seen)
                seen.add(edge.edge_idx)
        self.assertEqual(len(seen), matrix.num_edges)

if __name__ == "__main__":
    unittest.main()
