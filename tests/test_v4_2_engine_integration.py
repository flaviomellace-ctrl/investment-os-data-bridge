"""Investment OS V4.2 engine integration regression — synthetic only."""
from __future__ import annotations
import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V41_PATH = ROOT / "src" / "investment_os" / "v4_1_frozen" / "v4_scoring.py"
V42_PATH = ROOT / "src" / "investment_os" / "v4_2" / "v4_scoring.py"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

v41 = load("v41_frozen", V41_PATH)
v42 = load("v42_candidate", V42_PATH)

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

BASE = dict(
    module="GENERAL",
    op_margin=0.22, fcf_margin=0.18, roic=0.19, cash_conversion=1.05,
    margin_stability=0.05, retention=0.95, unit_cost_decline=0.02,
    revenue_cagr3=0.11, opinc_cagr3=0.12, fcf_cagr3=0.10, reinvestment_rate=0.09,
    share_change=-0.01, buyback_accretion=1.6, sbc_to_revenue=0.04,
    fcf_per_share_cagr3=0.11,
    net_debt_to_ocf=1.2, interest_coverage=9.0, accrual_quality=1.1,
    data_coverage_pct=100.0, market_cap=100e9, ocf=9e9, capex=1e9, sbc=0.6e9
)

# 1. Engine identity / V4.1 immutability.
check("I1 V4.2 engine has explicit version", v42.ENGINE_VERSION == "V4.2-PRE-FREEZE-1.0")
check("I2 V4.2 growth policy is G2", v42.GROWTH_POLICY == "G2_GUARDED_PER_SHARE")

# 2. BQS must remain identical because V4.2 did not change BQS.
archetypes = []
archetypes.append(copy.deepcopy(BASE))
a = copy.deepcopy(BASE); a["module"]="MARKETPLACE_NETWORK"; a.update(
    ebitda_on_volume=0.03, fcf_on_volume=0.025, take_rate=0.18,
    two_sided_growth=0.08, frequency_growth=0.04
); archetypes.append(a)
a = copy.deepcopy(BASE); a["module"]="UTILITY"; a["fcf_margin"]=v41.NA; archetypes.append(a)
a = copy.deepcopy(BASE); a["roic"]=None; archetypes.append(a)

for i, row in enumerate(archetypes, 1):
    b41 = v41.bqs(copy.deepcopy(row))
    b42 = v42.bqs(copy.deepcopy(row))
    check(f"I3.{i} BQS parity V4.1==V4.2", b41 == b42, f"{b41} vs {b42}")

# 3. G2 properties.
check("I4 G2 genuine 16% revenue / 27% FCF-share -> 15%",
      abs(v42.guarded_per_share_growth(0.16, 0.27) - 0.15) < 1e-12)
check("I5 G2 revenue-only acceleration gets no extra credit",
      abs(v42.guarded_per_share_growth(0.25, 0.06) - 0.06) < 1e-12)
check("I6 G2 cash-only acceleration gets no extra credit",
      abs(v42.guarded_per_share_growth(0.06, 0.25) - 0.06) < 1e-12)
check("I7 G2 missing stays unknown",
      v42.guarded_per_share_growth(None, 0.20) is None)

# 4. GENERAL numeric integration.
bg, cov, _, _ = v42.bqs(BASE)
ios42, d42 = v42.ios(BASE, bg, cov)
check("I8 GENERAL IOS remains calculable with complete inputs", ios42 is not None)
check("I9 GENERAL detail reports G2 policy", d42.get("growth_policy") == "G2_GUARDED_PER_SHARE")
check("I10 GENERAL DCF growth retains 12% prudential cap",
      d42.get("dcf_growth_used") <= 0.12)

genuine = copy.deepcopy(BASE)
genuine.update(revenue_cagr3=0.16, fcf_cagr3=0.30, fcf_per_share_cagr3=0.27)
b41, c41, _, _ = v41.bqs(genuine)
b42, c42, _, _ = v42.bqs(genuine)
i41, d41 = v41.ios(genuine, b41, c41)
i42, d42 = v42.ios(genuine, b42, c42)
check("I11 BQS unchanged on genuine inflection", b41 == b42)
check("I12 V4.2 recognizes 15% guarded growth", d42.get("growth_used") == 0.15)
check("I13 V4.2 expected return exceeds V4.1 when both growth signals support it",
      d42["exp_ret"] > d41["exp_ret"], f"{d42['exp_ret']} vs {d41['exp_ret']}")

# 5. Missing-data semantics tightened in IOS.
for field in ("capex", "sbc", "share_change", "fcf_per_share_cagr3"):
    row = copy.deepcopy(BASE)
    row[field] = None
    b, c, _, _ = v42.bqs(row)
    score, detail = v42.ios(row, b, c)
    check(f"I14 {field} MISSING blocks GENERAL IOS instead of becoming zero",
          score is None, str(detail))

# 6. Sector variants remain numerically identical where authorized.
BANK = dict(
    module="BANK", roe=0.14, margin_stability=0.03, retention=0.95,
    equity_to_assets=0.10, accrual_quality=1.1, net_margin=0.28,
    data_coverage_pct=100.0, market_cap=60e9,
    book_value=28e9, payout_ratio=0.45, share_change=-0.01,
    ocf=9e9, capex=0.4e9, sbc=0.3e9
)
INS = dict(
    module="INSURANCE", roe=0.13, combined_ratio=0.94, margin_stability=0.04,
    retention=0.93, net_margin=0.10, accrual_quality=1.05,
    net_debt_to_ocf=0.5, interest_coverage=12.0,
    data_coverage_pct=100.0, market_cap=30e9,
    book_value=18e9, payout_ratio=0.40, share_change=-0.01,
    ocf=4e9, capex=0.2e9, sbc=0.1e9
)
REIT = dict(
    module="REIT", ffo_margin=0.55, occupancy=0.97,
    net_debt_to_ocf=4.0, interest_coverage=3.5,
    margin_stability=0.05, retention=0.95, roic=0.08,
    revenue_cagr3=0.04, opinc_cagr3=0.04, fcf_cagr3=0.04,
    reinvestment_rate=0.04, share_change=-0.01, buyback_accretion=1.0,
    sbc_to_revenue=0.01, fcf_per_share_cagr3=0.04,
    accrual_quality=1.0, data_coverage_pct=100.0,
    market_cap=20e9, affo=1.3e9, ocf=3e9, capex=1e9, sbc=0.05e9
)

for name, row in (("BANK",BANK), ("INSURANCE",INS), ("REIT",REIT)):
    b41,c41,_,_ = v41.bqs(copy.deepcopy(row))
    b42,c42,_,_ = v42.bqs(copy.deepcopy(row))
    i41,d41 = v41.ios(copy.deepcopy(row), b41, c41)
    i42,d42 = v42.ios(copy.deepcopy(row), b42, c42)
    check(f"I15 {name} BQS parity", b41 == b42)
    check(f"I16 {name} IOS numeric parity", i41 == i42, f"{i41} vs {i42}")
    check(f"I17 {name} IOS variant parity", d41.get("variant") == d42.get("variant"))

# 7. Missing dilution also blocks non-GENERAL IOS.
for name, row in (("BANK",BANK), ("INSURANCE",INS), ("REIT",REIT)):
    x = copy.deepcopy(row); x["share_change"] = None
    b,c,_,_ = v42.bqs(x)
    s,d = v42.ios(x,b,c)
    check(f"I18 {name} missing dilution is not zero", s is None and "share_change" in d.get("gate",""))

# 8. Final BUY gate unchanged.
check("I19 NOT LIVE still blocks BUY",
      v42.can_emit_buy(False, True, False, False)[0] is False)
check("I20 unresolved red flag still blocks BUY",
      v42.can_emit_buy(True, True, True, False)[0] is False)

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)
print("V4.2 ENGINE INTEGRATION SYNTHETIC SUITE PASSED")
