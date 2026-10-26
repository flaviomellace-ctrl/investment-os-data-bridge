import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import br04_data14_market_refresh as m
import br04_historical_base as historical
import rebase_br04_data09 as base
import br04_data11_mcd as shares
import br04_data12_revenue as revenue
import split_for_claude as splitter
ROOT=Path(__file__).resolve().parents[1]
class MarketRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s1=(ROOT/'data/staging/br04/40122845921/candidate/sp500_fundamentals.csv').read_bytes()
        cls.old=historical.reconstruct(s1);cls.current=(ROOT/'data/current/sp500_fundamentals.csv').read_bytes()
        data,_=base.reconstruct(s1,(ROOT/'data/research/br04-data09/manifest.json').read_bytes())
        proof=(ROOT/'data/research/br04-data10/prior_rc1_proofs.json').read_bytes()
        data,_=shares.amend(data,proof);cls.data,_=revenue.amend(data,proof)
    def test_exact_refresh_preserves_all_fundamental_amendments(self):
        data,report,changes=m.rebase(self.old,self.current,self.data)
        self.assertEqual(report,json.loads((ROOT/'data/research/br04-data14/reconstruction.json').read_bytes()))
        self.assertEqual(len(changes),1506);self.assertEqual(report['legacy_amended_cells_preserved'],30)
        self.assertEqual({c['field'] for c in changes},m.MARKET_FIELDS)
        for a,b in zip(m.read(self.data)[1],m.read(data)[1]):
            self.assertEqual({k:v for k,v in a.items() if k not in m.MARKET_FIELDS},{k:v for k,v in b.items() if k not in m.MARKET_FIELDS})
        for k in ['historical_approvals_transferred','candidate_promoted','economic_clearance','buy_add_allowed']:self.assertFalse(report[k])
    def test_all_hash_pins_and_historical_input_reject_tampering(self):
        args=[self.old,self.current,self.data]
        for i in range(3):
            changed=list(args);changed[i]+=b' '
            with self.assertRaisesRegex(ValueError,'hash mismatch'):m.rebase(*changed)
        with self.assertRaisesRegex(ValueError,'current base hash'):m.rebase(self.old,self.old,self.data)
        with self.assertRaisesRegex(ValueError,'historical S1 hash'):historical.reconstruct(b'invalid')
    def test_transport_corruption_and_ranges_fail_closed(self):
        data,_,_=m.rebase(self.old,self.current,self.data)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'candidate.csv';source.write_bytes(data);index=splitter.split_file(source=source,output_dir=p,url_base=None)
            self.assertTrue(m.verify_transport(data,p,index)['reassembled_byte_identical'])
            index['parts'][0]['row_start_1_based']=2
            with self.assertRaisesRegex(ValueError,'range'):m.verify_transport(data,p,index)
            index['parts'][0]['row_start_1_based']=1
            chunk=p/index['parts'][0]['filename'];chunk.write_bytes(chunk.read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError,'chunk hash'):m.verify_transport(data,p,index)
