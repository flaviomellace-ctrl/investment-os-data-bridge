"""Regression checks for the byte-pinned accepted 0.3 BR04 builder."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / 'src/build_br04_candidate.py'
spec = importlib.util.spec_from_file_location('br04_accepted_regression', PATH)
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)

def fact(value, tag='FinanceLeaseLiability', adsh='fixture'):
    return {'value': value, 'tag': tag, 'adsh': adsh, 'ddate': '20251231', 'uom': 'USD', 'qtrs': '0'}

class AcceptedBuilderTests(unittest.TestCase):
    def test_exact_accepted_bytes(self):
        self.assertEqual(hashlib.sha256(PATH.read_bytes()).hexdigest(), 'fa3ac869c21bb9e71ff1fe22aa9b5aa060f11849dabe241fdadbc84cfdb53ec3')

    def test_missing_liability_not_equity_residual(self):
        self.assertIsNone(builder.liability_source_value(None))

    def test_invalid_liabilities_stay_missing(self):
        for value in [0, -1, float('nan'), float('inf'), 'bad']:
            with self.subTest(value=value):
                self.assertIsNone(builder.liability_source_value({'value': value}))

    def test_direct_liability_total_preserved(self):
        self.assertEqual(builder.liability_source_value({'value': 131836000000}), 131836000000)

    def test_lease_total_matches_components(self):
        used, status = builder.reconcile_lease_facts([fact(12)], [fact(5,'FinanceLeaseLiabilityCurrent')], [fact(7,'FinanceLeaseLiabilityNoncurrent')])
        self.assertEqual(status, 'PRESENT')
        self.assertEqual(builder.sum_items(used), 12)

    def test_lease_mismatch_stays_conflicting(self):
        used, status = builder.reconcile_lease_facts([fact(10)], [fact(5,'FinanceLeaseLiabilityCurrent')], [fact(7,'FinanceLeaseLiabilityNoncurrent')])
        self.assertEqual(status, 'CONFLICTING_TOTAL_COMPONENTS')
        self.assertEqual(builder.sum_items(used), 12)

    def test_scope_mismatch_stays_conflicting(self):
        _, status = builder.reconcile_lease_facts([fact(12)], [fact(5,adsh='different')], [fact(7)])
        self.assertEqual(status, 'CONFLICTING_SCOPE')

    def test_partial_lease_not_exact(self):
        _, status = builder.reconcile_lease_facts([], [fact(5,'FinanceLeaseLiabilityCurrent')], [])
        self.assertEqual(status, 'PARTIAL_COMPONENT')

    def test_inconsistent_duplicates_rejected(self):
        _, status = builder.reconcile_lease_facts([fact(12),fact(13)], [], [])
        self.assertEqual(status, 'CONFLICTING_VALUE')

    def test_add_only_uncovered_finance_piece(self):
        items, status = builder.reconcile_lease_facts([fact(12)], [fact(5,'FinanceLeaseLiabilityCurrent')], [fact(7,'FinanceLeaseLiabilityNoncurrent')])
        debt = [fact(100,'LongTermDebtAndCapitalLeaseObligationsCurrent')]
        value, _, conflict = builder.merge_finance_into_debt(100,debt,items,status)
        self.assertEqual(value,107)
        self.assertFalse(conflict)

    def test_combined_debt_does_not_double_count_finance(self):
        items, status = builder.reconcile_lease_facts([fact(12)], [fact(5,'FinanceLeaseLiabilityCurrent')], [fact(7,'FinanceLeaseLiabilityNoncurrent')])
        debt=[fact(100,'LongTermDebtAndCapitalLeaseObligationsCurrent'),fact(200,'LongTermDebtAndCapitalLeaseObligationsNoncurrent')]
        value, _, conflict=builder.merge_finance_into_debt(300,debt,items,status)
        self.assertEqual(value,300)
        self.assertFalse(conflict)

    def test_unknown_lease_allocation_stays_conflicting(self):
        value, _, conflict=builder.merge_finance_into_debt(100,[fact(100,'LongTermDebtAndCapitalLeaseObligationsCurrent')],[fact(12)],'PRESENT')
        self.assertEqual(value,100)
        self.assertTrue(conflict)

if __name__ == '__main__':
    unittest.main()
