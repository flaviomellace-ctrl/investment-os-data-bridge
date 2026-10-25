import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from br04_lease_regression import valid_partial_operating_lease

class PartialLeaseRegressionTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(ticker='TEST', annual_adsh='filing', br04_flags='OPERATING_LEASE_PARTIAL_COMPONENT', operating_lease_liabilities='', operating_lease_liabilities_components='OperatingLeaseLiabilityNoncurrent=100')
        self.fact = dict(ticker='TEST', adsh='filing', used_as='operating_lease_candidate_lower_bound', tag='OperatingLeaseLiabilityNoncurrent', value='100', stmt='BS', qtrs='0', uom='USD')

    def test_one_side_is_evidence_not_exact_total(self):
        self.assertTrue(valid_partial_operating_lease(self.row, [self.fact]))
        self.row['operating_lease_liabilities_components']='OperatingLeaseLiabilityCurrent=100'
        self.fact['tag']='OperatingLeaseLiabilityCurrent'
        self.assertTrue(valid_partial_operating_lease(self.row, [self.fact]))

    def test_bad_publications_rejected(self):
        mutations = [('operating_lease_liabilities','100'), ('operating_lease_liabilities','0'), ('br04_flags',''), ('br04_flags','OPERATING_LEASE_PARTIAL_COMPONENT;OPERATING_LEASE_CONFLICTING'), ('operating_lease_liabilities_components',''), ('operating_lease_liabilities_components','OperatingLeaseLiability=100'), ('operating_lease_liabilities_components','OperatingLeaseLiabilityNoncurrent=100;OperatingLeaseLiabilityCurrent=5'), ('operating_lease_liabilities_components','OperatingLeaseLiabilityNoncurrent=nan'), ('operating_lease_liabilities_components','OperatingLeaseLiabilityNoncurrent=-1'), ('operating_lease_liabilities_components','OperatingLeaseLiabilityNoncurrent=wrong')]
        for key,value in mutations:
            with self.subTest(key=key,value=value):
                self.assertFalse(valid_partial_operating_lease({**self.row,key:value},[self.fact]))

    def test_mismatched_provenance_rejected(self):
        for key,value in [('ticker','OTHER'),('adsh','other-filing'),('used_as','operating_lease_liabilities'),('tag','OperatingLeaseLiabilityCurrent'),('value','101'),('value','nan'),('stmt','CF'),('qtrs','4'),('uom','EUR')]:
            with self.subTest(key=key):
                self.assertFalse(valid_partial_operating_lease(self.row,[{**self.fact,key:value}]))

    def test_missing_duplicate_evidence_rejected(self):
        self.assertFalse(valid_partial_operating_lease(self.row,[]))
        self.assertFalse(valid_partial_operating_lease(self.row,[self.fact,self.fact]))

if __name__ == '__main__': unittest.main()
