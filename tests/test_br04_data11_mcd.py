import csv,io,json,unittest
from pathlib import Path
from src import br04_data11_mcd as m
from src import rebase_br04_data09 as rebase
ROOT=Path(__file__).resolve().parents[1]
class MCDTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data,_=rebase.reconstruct((ROOT/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes(),(ROOT/'data/research/br04-data09/manifest.json').read_bytes())
        cls.proof=(ROOT/'data/research/br04-data10/prior_rc1_proofs.json').read_bytes()
    def test_five_cell_scope_and_recomputed_growth(self):
        output,report=m.amend(self.data,self.proof)
        a=list(csv.DictReader(io.StringIO(self.data.decode())));b=list(csv.DictReader(io.StringIO(output.decode())))
        for old,new in zip(a,b):
            if old['ticker']!='MCD':self.assertEqual(old,new)
            else:
                self.assertEqual(new['fy_minus_3_diluted_shares'],'741300000.0')
                self.assertEqual(old['share_change'],new['share_change'])
                self.assertEqual(old['diluted_shares_yoy'],new['diluted_shares_yoy'])
                self.assertAlmostEqual(float(new['fcf_per_share_cagr3']),.10658225297861201)
        self.assertEqual(len(report['changed_cells']),5)
        self.assertEqual(report,json.loads((ROOT/'data/research/br04-data11/amendment.json').read_bytes()))
        for k in ['candidate_promoted','economic_clearance','buy_add_allowed','data09_s2_approval_inherited']:self.assertFalse(report[k])
    def test_tamper_and_double_application_rejected(self):
        for data,proof in [(self.data+b' ',self.proof),(self.data,self.proof+b' '),(m.amend(self.data,self.proof)[0],self.proof)]:
            with self.assertRaisesRegex(ValueError,'hash mismatch'):m.amend(data,proof)
