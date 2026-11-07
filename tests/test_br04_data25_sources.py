import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from br04_data25_share_sources import select
class SourceSelection(unittest.TestCase):
    def fact(self,**kw):
        return dict(dict(accn='a',start='2024-01-01',end='2024-12-31',filed='2025-02-01',form='10-K',fp='FY',val=100),**kw)
    def check(self,fs):return select(fs,'a','2024-12-31','2025-02-01')
    def test_exact(self):self.assertEqual(self.check([self.fact()])[0]['val'],100)
    def test_quarter_rejected(self):self.assertIsNone(self.check([self.fact(start='2024-10-01')])[0])
    def test_accession_rejected(self):self.assertIsNone(self.check([self.fact(accn='b')])[0])
    def test_ambiguous_rejected(self):self.assertIsNone(self.check([self.fact(),self.fact(val=200)])[0])
    def test_split_rejected(self):self.assertEqual(self.check([self.fact(),self.fact(accn='b',filed='2026-02-01',val=400)])[1],'LATER_RESTATEMENT_OR_SPLIT_REVIEW')
    def test_amended_value_rejected(self):self.assertIsNone(self.check([self.fact(),self.fact(accn='b',filed='2025-03-01',form='10-K/A',val=101)])[0])
    def test_consistent_later(self):self.assertIsNotNone(self.check([self.fact(),self.fact(accn='b',filed='2026-02-01')])[0])
if __name__=='__main__':unittest.main()
