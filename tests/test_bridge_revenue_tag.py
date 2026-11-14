import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import bridge

TAGS = bridge.FLOW_METRICS["revenue"]

def frame(rows):
    return pd.DataFrame([dict(adsh="A", tag=t, qtrs_num=4, uom="USD", value_num=v, ddate_num=d) for t, v, d in rows])

def test_total_revenue_preferred_when_larger_than_contract_revenue():
    df = frame([("RevenueFromContractWithCustomerExcludingAssessedTax", 60.0, 20251231), ("Revenues", 100.0, 20251231),
                ("RevenueFromContractWithCustomerExcludingAssessedTax", 50.0, 20241231), ("Revenues", 90.0, 20241231)])
    cur, tag, date, prior, pdate = bridge._pick_tag_values(df, "A", TAGS, 4, "USD")
    assert (cur, tag, date, prior, pdate) == (100.0, "Revenues", "20251231", 90.0, "20241231")

def test_contract_revenue_kept_when_it_is_the_only_or_equal_tag():
    df = frame([("RevenueFromContractWithCustomerExcludingAssessedTax", 60.0, 20251231)])
    assert bridge._pick_tag_values(df, "A", TAGS, 4, "USD")[:2] == (60.0, "RevenueFromContractWithCustomerExcludingAssessedTax")
    df = frame([("RevenueFromContractWithCustomerExcludingAssessedTax", 60.0, 20251231), ("Revenues", 60.0, 20251231)])
    assert bridge._pick_tag_values(df, "A", TAGS, 4, "USD")[:2] == (60.0, "RevenueFromContractWithCustomerExcludingAssessedTax")

def test_total_from_an_older_period_is_not_used():
    df = frame([("RevenueFromContractWithCustomerExcludingAssessedTax", 60.0, 20251231), ("Revenues", 100.0, 20241231)])
    assert bridge._pick_tag_values(df, "A", TAGS, 4, "USD")[:2] == (60.0, "RevenueFromContractWithCustomerExcludingAssessedTax")
