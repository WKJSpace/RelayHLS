"""Offline release checks: exercise real malformed-input and metric failures."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ReleaseChecks(unittest.TestCase):
    def load_checks(self):
        path=ROOT/'scripts/verify_release.py'
        self.assertTrue(path.is_file(), 'The release verifier must exist')
        spec=importlib.util.spec_from_file_location('release_checks', path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_all_public_fixtures_are_well_formed(self):
        check=self.load_checks()
        for path in sorted((ROOT/'benchmarks').glob('bb*/*/config.json')):
            with self.subTest(path=str(path.parent.relative_to(ROOT))):
                self.assertEqual(check.verify_fixture(path.parent)['cases'],32)

    def test_incomplete_syndrome_rejected(self):
        check=self.load_checks()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            source=ROOT/'benchmarks/bb144/c4v8'
            for name in ['config.json','golden.txt']:(path/name).write_bytes((source/name).read_bytes())
            values=(source/'inputs.txt').read_text().split()
            (path/'inputs.txt').write_text(' '.join(values[:-1]))
            with self.assertRaisesRegex(ValueError,'input layout'):check.verify_fixture(path)

    def test_wrong_golden_width_rejected(self):
        check=self.load_checks()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);source=ROOT/'benchmarks/bb72/c4v8'
            for name in ['config.json','inputs.txt']:(path/name).write_bytes((source/name).read_bytes())
            lines=(source/'golden.txt').read_text().splitlines();fields=lines[0].split();fields[3]=fields[3][:-1];lines[0]=' '.join(fields)
            (path/'golden.txt').write_text('\n'.join(lines)+'\n')
            with self.assertRaisesRegex(ValueError,'golden width'):check.verify_fixture(path)

    def test_reject_other_bb144_points(self):
        check=self.load_checks()
        with self.assertRaisesRegex(ValueError,'BB144 selection'):
            check.verify_selection({'BB72':[f'C{c}V{v}' for c in [1,2,4] for v in [2,4,8]],'BB144':['C4V8','C2V8']})

    def test_service_rate_uses_31_intervals(self):
        check=self.load_checks()
        self.assertAlmostEqual(check.service_rate(3296545,31,100),940.3784871736924)
        with self.assertRaisesRegex(ValueError,'31 service intervals'):check.service_rate(3296545,32,100)

if __name__=='__main__':unittest.main()
