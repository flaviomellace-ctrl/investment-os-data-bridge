import csv,io,json,unittest
from pathlib import Path
from src import br04_data12_revenue as r
from src import br04_data11_mcd as m
from src import rebase_br04_data09 as base
ROOT=Path(__file__).resolve().parents[1]
class RevenueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=(ROOT/'data/research/br04-data10/prior_rc1_proofs.json').read_bytes()
        data,_=base.reconstruct((ROOT/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes(),(ROOT/'data/research/br04-data09/manifest.json').read_bytes())
        cls.data,_=m.amend(data,cls.proof)
    def test_scope_provenance_and_reproducible_receipt(self):
        data,report=r.amend(self.data,self.proof)
        self.assertEqual(report,json.loads((ROOT/'data/research/br04-data12/amendment.json').read_bytes()))
        self.assertEqual(report['changed_cells'],25)
        before=list(csv.DictReader(io.StringIO(self.data.decode())));after=list(csv.DictReader(io.StringIO(data.decode())))
        for a,b in zip(before,after):
            if a['ticker'] not in ['CEG','WELL']:self.assertEqual(a,b)
            self.assertEqual(list(a.items())[212:],list(b.items())[212:])
        self.assertEqual(len(report['field_provenance']),10)
        for k in ['prior_approvals_inherited','candidate_promoted','economic_clearance','buy_add_allowed']:self.assertFalse(report[k])
    def test_homogeneous_revenues_and_dependent_metrics(self):
        data,_=r.amend(self.data,self.proof);rows={x['ticker']:x for x in csv.DictReader(io.StringIO(data.decode()))}
        for ticker,expected in [('CEG',[25533000000,23568000000,24918000000,24440000000]),('WELL',[10838034000,7991118000,6637995000,5860615000])]:
            x=rows[ticker]
            for pre,value in zip(['annual_','fy_minus_1_','fy_minus_2_','fy_minus_3_'],expected):
                self.assertEqual(float(x[pre+'revenue']),value);self.assertEqual(x[pre+'revenue_tag'],'Revenues')
            self.assertAlmostEqual(float(x['revenue_yoy']),expected[0]/expected[1]-1)
            self.assertAlmostEqual(float(x['revenue_cagr3']),(expected[0]/expected[3])**(1/3)-1)
            self.assertAlmostEqual(float(x['net_margin']),float(x['annual_net_income'])/expected[0])
        ceg=rows['CEG'];self.assertEqual(ceg['annual_revenue_date'],'20251231.0');self.assertEqual(ceg['core_metric_coverage_pct'],'100.0');self.assertEqual(ceg['data_quality_flags'],'OK')
        self.assertEqual(rows['WELL']['operating_margin'],'');self.assertEqual(rows['WELL']['fcf_margin'],'')
    def test_tampering_and_double_application_rejected(self):
        for data,proof in [(self.data+b' ',self.proof),(self.data,self.proof+b' '),(r.amend(self.data,self.proof)[0],self.proof)]:
            with self.assertRaisesRegex(ValueError,'hash mismatch'):r.amend(data,proof)
