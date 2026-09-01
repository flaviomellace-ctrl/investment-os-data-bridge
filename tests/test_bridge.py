import io
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import bridge


class BridgeTests(unittest.TestCase):
    def test_normalize_ticker(self):
        self.assertEqual(bridge.normalize_ticker("brk.b"), "BRK-B")
        self.assertEqual(bridge.normalize_ticker(" AAPL "), "AAPL")


    def test_parse_state_street_xlsx(self):
        raw = pd.DataFrame([
            ["SPDR S&P 500 ETF Trust", None, None],
            ["Holdings as of Aug 28, 2026", None, None],
            ["Name", "Ticker", "Weight"],
            ["Alpha Inc", "AAA", 1.2],
            ["US DOLLAR", "USD", 0.1],
        ])
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            raw.to_excel(writer, index=False, header=False)
        universe, meta = bridge.parse_state_street_xlsx(bio.getvalue())
        self.assertEqual(len(universe), 1)
        self.assertEqual(universe.iloc[0]["ticker"], "AAA")
        self.assertEqual(meta["data_as_of"], "2026-08-28")

    def test_pick_flow_current_and_prior(self):
        df = pd.DataFrame(
            [
                {"adsh": "A", "tag": "Revenues", "qtrs_num": 4, "uom": "USD", "value_num": 100.0, "ddate_num": 20251231},
                {"adsh": "A", "tag": "Revenues", "qtrs_num": 4, "uom": "USD", "value_num": 90.0, "ddate_num": 20241231},
            ]
        )
        cur, tag, ddate, prior, prior_date = bridge._pick_tag_values(df, "A", ["Revenues"], 4, "USD")
        self.assertEqual(cur, 100.0)
        self.assertEqual(prior, 90.0)
        self.assertEqual(tag, "Revenues")
        self.assertEqual(ddate, "20251231")
        self.assertEqual(prior_date, "20241231")

    def test_pick_instant(self):
        df = pd.DataFrame(
            [
                {"adsh": "A", "tag": "Assets", "qtrs_num": 0, "uom": "USD", "value_num": 200.0, "ddate_num": 20251231},
                {"adsh": "A", "tag": "Assets", "qtrs_num": 0, "uom": "USD", "value_num": 180.0, "ddate_num": 20241231},
            ]
        )
        val, tag, ddate = bridge._pick_instant(df, "A", ["Assets"], "USD")
        self.assertEqual(val, 200.0)
        self.assertEqual(tag, "Assets")
        self.assertEqual(ddate, "20251231")

    def test_build_fundamentals(self):
        universe = pd.DataFrame([
            {"ticker": "AAA", "ticker_sec": "AAA", "name": "AAA Inc", "sector": "Tech", "weight": 1.0, "cik": "0000000001"}
        ])
        selected = pd.DataFrame([
            {
                "cik": "0000000001", "filing_kind": "annual", "sic": "3571", "form": "10-K",
                "period": "20251231", "filed": "20260215", "adsh": "A"
            }
        ])
        rows = []
        def add(tag, qtrs, value, ddate, uom="USD"):
            rows.append({"adsh": "A", "tag": tag, "qtrs_num": qtrs, "uom": uom, "value_num": value, "ddate_num": ddate})
        add("Revenues", 4, 1000, 20251231)
        add("Revenues", 4, 900, 20241231)
        add("NetIncomeLoss", 4, 100, 20251231)
        add("OperatingIncomeLoss", 4, 150, 20251231)
        add("NetCashProvidedByUsedInOperatingActivities", 4, 200, 20251231)
        add("PaymentsToAcquirePropertyPlantAndEquipment", 4, 50, 20251231)
        add("WeightedAverageNumberOfDilutedSharesOutstanding", 4, 10, 20251231, "shares")
        add("WeightedAverageNumberOfDilutedSharesOutstanding", 4, 9.5, 20241231, "shares")
        add("Assets", 0, 1200, 20251231)
        add("StockholdersEquity", 0, 600, 20251231)
        add("CashAndCashEquivalentsAtCarryingValue", 0, 100, 20251231)
        add("LongTermDebt", 0, 200, 20251231)
        nums = pd.DataFrame(rows)
        fundamentals, coverage = bridge.build_fundamentals(universe, selected, nums, ["2026Q1", "2026Q2"])
        r = fundamentals.iloc[0]
        self.assertEqual(r["annual_fcf"], 150)
        self.assertAlmostEqual(r["revenue_yoy"], 1000 / 900 - 1)
        self.assertAlmostEqual(r["operating_margin"], 0.15)
        self.assertEqual(r["data_status"], "PRESENT")
        self.assertEqual(len(coverage), 1)


if __name__ == "__main__":
    unittest.main()
