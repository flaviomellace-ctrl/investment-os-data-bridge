import json,unittest
from pathlib import Path
from src import br04_data13_inventory as inv
from src import br04_data12_revenue as rev
from src import br04_data11_mcd as mcd
from src import rebase_br04_data09 as base
ROOT=Path(__file__).resolve().parents[1]
class CurrentInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=ROOT/'data/research/br04-data10';cls.ledger=(d/'prior_rc1_ledger.csv').read_bytes();cls.proof=(d/'prior_rc1_proofs.json').read_bytes()
        data,_=base.reconstruct((ROOT/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes(),(ROOT/'data/research/br04-data09/manifest.json').read_bytes())
        data,_=mcd.amend(data,cls.proof);cls.data,_=rev.amend(data,cls.proof)
    def test_current_gaps_and_unresolved_numerator(self):
        summary,rows,diffs=inv.inventory(self.data,self.ledger,self.proof)
        self.assertEqual(summary,json.loads((ROOT/'data/research/br04-data13/open_items.json').read_bytes()))
        self.assertEqual(summary['rows_with_listed_open_items'],379)
        self.assertEqual(summary['prior_ledger_substantive_differences'],1)
        material=[x for x in diffs if x['classification']=='SUBSTANTIVE_REVIEW_REQUIRED']
        self.assertEqual([(x['ticker'],x['field'],x['current']) for x in material],[('CEG','sbc_to_revenue','')])
        ceg=next(x for x in rows if x['ticker']=='CEG');self.assertIn('MISSING_ANNUAL_SBC',ceg['reasons'])
        for row in rows:
            self.assertFalse(row['buy_add_allowed']);self.assertFalse(row['economic_clearance']);self.assertFalse(row['system_live'])
            self.assertNotIn('DOCUMENTED_SHARE_UNIT_CORRECTION_NOT_REAPPLIED',row['reasons'])
            self.assertNotIn('PRIOR_REVENUE_POLICY_REQUIRES_RECONCILIATION',row['reasons'])
    def test_all_pinned_inputs_reject_tampering(self):
        args=[self.data,self.ledger,self.proof]
        for i in range(3):
            changed=list(args);changed[i]+=b' '
            with self.assertRaisesRegex(ValueError,'hash mismatch'):inv.inventory(*changed)
