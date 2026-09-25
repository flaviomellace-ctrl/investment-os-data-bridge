"""V4.2 R8 sector-variant regression. Synthetic only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "src" / "investment_os" / "v4_1_frozen"
sys.path.insert(0, str(FROZEN))

from v4_scoring import (
    NA,
    bqs,
    discount_rate,
    economics_spec,
    ios,
    ios_variant,
)

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}: {detail}")

# Routing invariants.
check("R8 GENERAL -> IOS_GENERAL", ios_variant("GENERAL") == "IOS_GENERAL")
check("R8 SOFTWARE -> IOS_GENERAL", ios_variant("SOFTWARE") == "IOS_GENERAL")
check("R8 MARKETPLACE_NETWORK -> IOS_GENERAL", ios_variant("MARKETPLACE_NETWORK") == "IOS_GENERAL")
check("R8 BANK -> IOS_BANK", ios_variant("BANK") == "IOS_BANK")
check("R8 ASSETMGR_EXCH -> IOS_BANK", ios_variant("ASSETMGR_EXCH") == "IOS_BANK")
check("R8 INSURANCE -> IOS_INSURANCE", ios_variant("INSURANCE") == "IOS_INSURANCE")
check("R8 REIT -> IOS_REIT", ios_variant("REIT") == "IOS_REIT")

# Marketplace economics stays volume-based.
mkt = economics_spec("MARKETPLACE_NETWORK")
mkt_keys = [x[0] for x in mkt]
check("R8 marketplace economics include EBITDA/volume", "ebitda_on_volume" in mkt_keys)
check("R8 marketplace economics include FCF/volume", "fcf_on_volume" in mkt_keys)
check("R8 marketplace economics include take rate", "take_rate" in mkt_keys)
check("R8 marketplace economics exclude op-margin scoring", "op_margin" not in mkt_keys)

# Discount-rate routing remains unchanged.
check("R8 marketplace receives model-risk premium",
      discount_rate("MARKETPLACE_NETWORK", 1.0, 80.0) == 0.105)
check("R8 general base discount unchanged",
      discount_rate("GENERAL", 1.0, 80.0) == 0.095)

# Synthetic bank: plentiful OCF cannot bypass equity-capital valuation.
bank = dict(
    module="BANK", roe=0.14, margin_stability=0.03, retention=0.95,
    equity_to_assets=0.10, accrual_quality=1.1, net_margin=0.28,
    data_coverage_pct=100.0, market_cap=60e9, ocf=9e9, capex=0.4e9, sbc=0.3e9
)
sb, cb, _, _ = bqs(bank)
ib, db = ios(bank, sb, cb)
check("R8 bank without book-value basis cannot fall back to general OCF IOS",
      ib is None and db.get("variant") == "IOS_BANK")

bank_ok = dict(bank, book_value=28e9, payout_ratio=0.45)
ib2, db2 = ios(bank_ok, sb, cb)
check("R8 bank with required capital inputs is calculable",
      ib2 is not None and db2.get("variant") == "IOS_BANK")
check("R8 bank basis remains normalized equity earnings",
      str(db2.get("basis", "")).startswith("utile normalizzato"))

# Insurance needs combined ratio.
ins = dict(
    module="INSURANCE", roe=0.13, combined_ratio=0.94, margin_stability=0.04,
    retention=0.93, net_margin=0.10, accrual_quality=1.05,
    net_debt_to_ocf=0.5, interest_coverage=12.0,
    data_coverage_pct=100.0, market_cap=30e9,
    book_value=18e9, payout_ratio=0.40,
    ocf=4e9, capex=0.2e9, sbc=0.1e9
)
si, ci, _, _ = bqs(ins)
ii, di = ios(ins, si, ci)
check("R8 insurer with combined ratio uses IOS_INSURANCE",
      ii is not None and di.get("variant") == "IOS_INSURANCE")
ins_missing = dict(ins, combined_ratio=None)
ii2, di2 = ios(ins_missing, si, ci)
check("R8 insurer missing combined ratio gets no approximated IOS",
      ii2 is None and "combined ratio" in di2.get("gate", ""))

# REIT needs AFFO; general OCF must not substitute.
reit = dict(
    module="REIT", ffo_margin=0.55, occupancy=0.97,
    net_debt_to_ocf=4.0, interest_coverage=3.5,
    margin_stability=0.05, retention=0.95, roic=0.08,
    revenue_cagr3=0.04, opinc_cagr3=0.04, fcf_cagr3=0.04,
    reinvestment_rate=0.04, share_change=0.0, buyback_accretion=1.0,
    sbc_to_revenue=0.01, fcf_per_share_cagr3=0.04,
    accrual_quality=1.0, data_coverage_pct=100.0,
    market_cap=20e9, ocf=3e9, capex=1e9, sbc=0.05e9
)
sr, cr, _, _ = bqs(reit)
ir, dr = ios(reit, sr, cr)
check("R8 REIT without AFFO cannot use general owner earnings",
      ir is None and dr.get("variant") == "IOS_REIT")
reit_ok = dict(reit, affo=1.3e9)
ir2, dr2 = ios(reit_ok, sr, cr)
check("R8 REIT with AFFO uses IOS_REIT",
      ir2 is not None and dr2.get("variant") == "IOS_REIT")
check("R8 REIT basis remains AFFO", dr2.get("basis") == "AFFO")

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)
print("R8 SECTOR-VARIANT REGRESSION PASSED")
