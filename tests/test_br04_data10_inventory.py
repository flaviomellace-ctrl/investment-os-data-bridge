import json
import unittest
from pathlib import Path
from src import br04_data10_inventory as inv
from src import rebase_br04_data09 as rebase
ROOT=Path(__file__).resolve().parents[1]
class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data,_=rebase.reconstruct((ROOT/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes(),(ROOT/'data/research/br04-data09/manifest.json').read_bytes())
        directory=ROOT/'data/research/br04-data10'
        cls.ledger=(directory/'prior_rc1_ledger.csv').read_bytes();cls.proof=(directory/'prior_rc1_proofs.json').read_bytes()
    def test_known_unit_problem_and_release_blocks(self):
        summary,rows,diffs=inv.inventory(self.data,self.ledger,self.proof)
        self.assertEqual(summary['prior_ledger_substantive_by_ticker'],{'MCD':5,'CEG':10,'WELL':11})
        self.assertEqual(summary['prior_ledger_formatting_only'],5)
        mcd=next(r for r in rows if r['ticker']=='MCD')
        self.assertIn('DOCUMENTED_SHARE_UNIT_CORRECTION_NOT_REAPPLIED',mcd['reasons'])
        self.assertTrue(all(not r['buy_add_allowed'] and not r['economic_clearance'] for r in rows))
        self.assertEqual(summary,json.loads((ROOT/'data/research/br04-data10/open_items.json').read_text()))
        self.assertTrue(all(not r['applied'] for r in diffs))
    def test_finite_presence_zero_not_missing(self):
        self.assertEqual(inv.number('0'),0)
        for value in ['',None,'NaN','Infinity','NOT_APPLICABLE']:
            self.assertIsNone(inv.number(value))
    def test_each_input_tamper_rejected(self):
        args=[self.data,self.ledger,self.proof]
        for i in range(3):
            with self.subTest(i=i):
                changed=list(args);changed[i]+=b' '
                with self.assertRaisesRegex(ValueError,'hash mismatch'):inv.inventory(*changed)
