import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from src import rebase_br04_data09 as rebase

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT/'data/research/br04-data09'

class RebaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes()
        cls.manifest = (DIR/'manifest.json').read_bytes()

    def test_reconstruction_exact_and_protected(self):
        result, report = rebase.reconstruct(self.source, self.manifest)
        self.assertEqual(hashlib.sha256(result).hexdigest(), 'a07152b3156b4dcfed065db3fe613a919604d4093084275c530d533695996449')
        self.assertEqual(report['changed_cells'], 75)
        self.assertEqual(report['leverage_indeterminate'], 212)
        self.assertNotIn('CONFLICTING', report['br04_status'])
        self.assertFalse(report['buy_add_allowed'])
        self.assertFalse(report['regression_s2_for_new_hash'])

    def test_input_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError, 'input byte hash'):
            rebase.reconstruct(self.source+b'\n', self.manifest)

    def test_manifest_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError, 'manifest byte hash'):
            rebase.reconstruct(self.source, self.manifest+b' ')

    def test_semantic_guards_even_with_re_pinned_manifest(self):
        for mutation, error in [
            (lambda m: m['changes'][0].update(field='annual_cash'), 'edit scope'),
            (lambda m: m['changes'][0].update(before='incorrect'), 'old value'),
            (lambda m: m['filings']['CVX'].update(annual_adsh='different'), 'filing identity'),
            (lambda m: m['changes'].append(m['changes'][0]), 'duplicate edit'),
            (lambda m: next(c for c in m['changes'] if c['ticker']=='MET' and c['field']=='net_debt_to_ocf').update(after='-0.0875848350105312'), 'no exact leverage'),
        ]:
            with self.subTest(error=error):
                m=json.loads(self.manifest);mutation(m);b=json.dumps(m).encode()
                with patch.object(rebase,'MANIFEST_SHA',hashlib.sha256(b).hexdigest()):
                    with self.assertRaisesRegex(ValueError,error): rebase.reconstruct(self.source,b)
