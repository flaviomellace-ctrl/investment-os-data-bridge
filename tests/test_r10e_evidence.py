import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import r10e_reconciliation_evidence as evidence


class EvidenceTests(unittest.TestCase):
    def fact(self, values):
        return {"facts": {"us-gaap": {"DA": {"units": {"USD": values}}}}}

    def select(self, values):
        return evidence.exact_annual_fact(self.fact(values), [("us-gaap", "DA", "USD")], "sealed", "2025-12-31")

    def annual(self, **updates):
        return dict({"accn": "sealed", "form": "10-K", "start": "2025-01-01", "end": "2025-12-31", "val": 100}, **updates)

    def test_annual_not_quarterly_or_later_filing(self):
        self.assertEqual(self.select([self.annual(start="2025-10-01", val=999), self.annual(accn="newer", val=800), self.annual()])["value"], 100)

    def test_conflict_not_silently_largest(self):
        self.assertEqual(self.select([self.annual(), self.annual(val=200)])["status"], "CONFLICTING")

    def test_zero_is_present_and_missing_is_missing(self):
        self.assertEqual(self.select([self.annual(val=0)])["value"], 0)
        self.assertEqual(self.select([])["status"], "MISSING")

    def test_wrong_period_never_falls_back(self):
        self.assertEqual(self.select([self.annual(end="2025-11-28")])["status"], "MISSING")

    def test_negation_is_review_not_auto_clear(self):
        r = evidence.contexts("we have no off-balance sheet arrangements.")
        self.assertEqual(r["off_balance"]["status"], "REVIEW_REQUIRED")
        self.assertIn("no off-balance", r["off_balance"]["matches"][0]["text"])
        self.assertEqual(r["guarantees"]["status"], "NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()
