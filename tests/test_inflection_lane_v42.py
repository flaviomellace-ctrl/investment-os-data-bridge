from inflection_lane_v42 import (
    LANE_I_QUOTA,
    LANE_V_QUOTA,
    baseline_growth_v41,
    blended_growth_candidate,
    guarded_per_share_growth_candidate,
    growth_bakeoff,
    inflection_assessment,
    merge_deep_dive_queue,
    rank_lane_i,
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

# Synthetic archetypes only. These are not real companies/tickers.
ARCH = {
    "A_GENUINE_INFLECTION": dict(
        entity_key="SYN_A", bqs=78, owner_earnings=8.0,
        revenue_cagr3=0.16, fcf_cagr3=0.30, fcf_per_share_cagr3=0.27,
        cash_conversion=1.05, share_change=-0.01, growth_flags=[], quality_flags=[]
    ),
    "B_MATURE_COMPOUNDER": dict(
        entity_key="SYN_B", bqs=88, owner_earnings=9.0,
        revenue_cagr3=0.09, fcf_cagr3=0.10, fcf_per_share_cagr3=0.11,
        cash_conversion=1.02, share_change=-0.01, growth_flags=[], quality_flags=[]
    ),
    "C_ONE_OFF_FAKE_INFLECTION": dict(
        entity_key="SYN_C", bqs=76, owner_earnings=10.0,
        revenue_cagr3=0.05, fcf_cagr3=0.35, fcf_per_share_cagr3=0.34,
        cash_conversion=1.30, share_change=0.00,
        growth_flags=["PRIOR_YEAR_ONE_OFF_SUSPECTED"], quality_flags=[]
    ),
    "D_WORKING_CAPITAL_OR_FLOAT_BOOST": dict(
        entity_key="SYN_D", bqs=74, owner_earnings=10.0,
        revenue_cagr3=0.10, fcf_cagr3=0.28, fcf_per_share_cagr3=0.27,
        cash_conversion=1.25, share_change=0.00,
        growth_flags=[], quality_flags=["CASH_QUALITY_RECONCILIATION_REQUIRED"]
    ),
    "E_CYCLICAL_REBOUND": dict(
        entity_key="SYN_E", bqs=72, owner_earnings=7.0,
        revenue_cagr3=0.06, fcf_cagr3=0.40, fcf_per_share_cagr3=0.38,
        cash_conversion=1.10, share_change=0.00,
        growth_flags=[], quality_flags=[], cyclical_rebound_flag=True
    ),
    "F_DILUTION_FUNDED_GROWTH": dict(
        entity_key="SYN_F", bqs=73, owner_earnings=6.0,
        revenue_cagr3=0.25, fcf_cagr3=0.25, fcf_per_share_cagr3=0.06,
        cash_conversion=0.95, share_change=0.08, growth_flags=[], quality_flags=[]
    ),
    "G_REVENUE_WITHOUT_CASH": dict(
        entity_key="SYN_G", bqs=79, owner_earnings=2.0,
        revenue_cagr3=0.25, fcf_cagr3=0.04, fcf_per_share_cagr3=0.03,
        cash_conversion=0.45, share_change=0.01, growth_flags=[], quality_flags=[]
    ),
    "H_CASH_GROWTH_DECLINING_REVENUE": dict(
        entity_key="SYN_H", bqs=80, owner_earnings=8.0,
        revenue_cagr3=-0.03, fcf_cagr3=0.25, fcf_per_share_cagr3=0.27,
        cash_conversion=1.10, share_change=-0.01, growth_flags=[], quality_flags=[]
    ),
}

# R4 lane behavior.
a = inflection_assessment(ARCH["A_GENUINE_INFLECTION"])
check("R4 genuine inflection is eligible", a["eligible"])
check("R4 genuine inflection is high confidence", a["high_confidence"])

b = inflection_assessment(ARCH["B_MATURE_COMPOUNDER"])
check("R4 mature compounder is not falsely called inflection", not b["eligible"])

c = inflection_assessment(ARCH["C_ONE_OFF_FAKE_INFLECTION"])
check("R4 one-off may meet raw floors but is not high confidence",
      c["eligible"] and not c["high_confidence"] and c["confidence"] == "PROVISIONAL")

d = inflection_assessment(ARCH["D_WORKING_CAPITAL_OR_FLOAT_BOOST"])
check("R4 cash-quality flag blocks high-confidence inflection",
      d["eligible"] and not d["high_confidence"])

e = inflection_assessment(ARCH["E_CYCLICAL_REBOUND"])
check("R4 cyclical rebound flag blocks high-confidence inflection",
      e["eligible"] and not e["high_confidence"])

f = inflection_assessment(ARCH["F_DILUTION_FUNDED_GROWTH"])
check("R4 dilution-funded growth fails eligibility", not f["eligible"])

g = inflection_assessment(ARCH["G_REVENUE_WITHOUT_CASH"])
check("R4 revenue without cash conversion fails eligibility", not g["eligible"])

h = inflection_assessment(ARCH["H_CASH_GROWTH_DECLINING_REVENUE"])
check("R4 cash growth with declining revenue fails eligibility", not h["eligible"])

ranked = rank_lane_i(list(ARCH.values()))
check("R4 only genuine synthetic inflection reaches high-confidence Lane I",
      [r["entity_key"] for r in ranked] == ["SYN_A"], str([r["entity_key"] for r in ranked]))

# R5 growth-treatment bake-off.
# Pre-registered desired behavior: genuine inflection gets >=12%;
# mature <=10%; one-off/cyclical/dilution/no-cash <=8%; working-capital <=10%;
# declining revenue <=2%.
limits = {
    "A_GENUINE_INFLECTION": ("min", 0.12),
    "B_MATURE_COMPOUNDER": ("max", 0.10),
    "C_ONE_OFF_FAKE_INFLECTION": ("max", 0.08),
    "D_WORKING_CAPITAL_OR_FLOAT_BOOST": ("max", 0.10),
    "E_CYCLICAL_REBOUND": ("max", 0.08),
    "F_DILUTION_FUNDED_GROWTH": ("max", 0.08),
    "G_REVENUE_WITHOUT_CASH": ("max", 0.08),
    "H_CASH_GROWTH_DECLINING_REVENUE": ("max", 0.02),
}

scores = {"G0_V41_BASELINE": 0, "G1_BLENDED": 0, "G2_GUARDED_PER_SHARE": 0}

for name, row in ARCH.items():
    vals = growth_bakeoff(
        revenue_cagr3=row["revenue_cagr3"],
        fcf_cagr3=row["fcf_cagr3"],
        fcf_per_share_cagr3=row["fcf_per_share_cagr3"],
    )
    mode, threshold = limits[name]
    for k, v in vals.items():
        ok = (v >= threshold) if mode == "min" else (v <= threshold)
        if ok:
            scores[k] += 1
    print(name, vals)

check("R5 baseline misses at least one required synthetic behavior",
      scores["G0_V41_BASELINE"] < len(ARCH), str(scores))
check("R5 blended candidate has false-positive weakness",
      scores["G1_BLENDED"] < len(ARCH), str(scores))
check("R5 guarded per-share treatment passes all pre-registered archetype behaviors",
      scores["G2_GUARDED_PER_SHARE"] == len(ARCH), str(scores))

# Monotonicity / guard properties for G2.
g_low = guarded_per_share_growth_candidate(0.10, 0.10)
g_high = guarded_per_share_growth_candidate(0.14, 0.14)
check("R5 G2 monotonic when both underlying growth rates rise", g_high >= g_low)
check("R5 G2 revenue-only acceleration receives no extra credit",
      guarded_per_share_growth_candidate(0.25, 0.06) == 0.06)
check("R5 G2 cash-only acceleration receives no extra credit",
      guarded_per_share_growth_candidate(0.06, 0.25) == 0.06)
check("R5 G2 hard cap is 15%",
      guarded_per_share_growth_candidate(0.30, 0.30) == 0.15)
check("R5 G2 does not convert missing input into zero",
      guarded_per_share_growth_candidate(None, 0.20) is None)

# Frozen 7+3 merge policy.
lane_v = [{"entity_key": f"V{i}", "ios": 100-i} for i in range(1, 11)]
lane_i = [
    {"entity_key": "I1", "score": 95},
    {"entity_key": "V3", "score": 94},  # duplicate should be skipped
    {"entity_key": "I2", "score": 93},
    {"entity_key": "I3", "score": 92},
]
merged = merge_deep_dive_queue(lane_v, lane_i)
keys = [x["entity_key"] for x in merged]
check("R4 merge total remains 10", len(merged) == 10, str(keys))
check("R4 merge takes first 7 valuation names", keys[:7] == [f"V{i}" for i in range(1,8)], str(keys))
check("R4 merge dedupes and fills 3 distinct Lane-I slots",
      keys[7:] == ["I1", "I2", "I3"], str(keys))

# Backfill if Lane I has insufficient names.
merged2 = merge_deep_dive_queue(lane_v, [{"entity_key": "I1", "score": 95}])
keys2 = [x["entity_key"] for x in merged2]
check("R4 insufficient Lane-I candidates backfill from valuation lane",
      len(merged2) == 10 and keys2[-2:] == ["V8", "V9"], str(keys2))

print("\nBAKEOFF_SCORES", scores)
print(f"PASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)
print("R4/R5 SYNTHETIC SUITE PASSED")
