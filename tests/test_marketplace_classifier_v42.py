import inspect
from marketplace_classifier_v42 import (
    CLASSIFIER_VERSION,
    CONFLICTING,
    MISSING,
    PRESENT,
    PROVISIONAL,
    VERIFIED,
    Evidence,
    MetricPoint,
    classify_marketplace,
    definition_drift_status,
    normalize_marketplace_kpis,
    ratio_metric,
    triage_marketplace,
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

PRIMARY = Evidence(
    source_type="PRIMARY",
    source_url_or_accession="synthetic-primary-document",
    filing_date="2026-01-01",
    classification_as_of="2026-01-01",
    evidence_excerpt_or_hash="synthetic-evidence-hash",
)

# R2-A — true two-sided marketplace.
tri = triage_marketplace(
    agency_or_net_presentation=True,
    capital_light_intermediation=True,
    intermediation_language=True,
)
res = classify_marketplace(
    original_module="GENERAL",
    candidate_marketplace=tri["candidate_marketplace"],
    two_sided_intermediation=True,
    revenue_linked_to_underlying_volume=True,
    company_reports_underlying_volume=True,
    evidence=PRIMARY,
)
check("R2-A triage candidate", tri["candidate_marketplace"] is True)
check("R2-A true marketplace routes to MARKETPLACE_NETWORK",
      res["final_module"] == "MARKETPLACE_NETWORK" and res["classification_status"] == VERIFIED)

# R2-B — SaaS vendor using 'platform' language is not enough.
tri_b = triage_marketplace(
    agency_or_net_presentation=False,
    capital_light_intermediation=False,
    intermediation_language=True,
)
res_b = classify_marketplace(
    original_module="SOFTWARE",
    candidate_marketplace=tri_b["candidate_marketplace"],
    two_sided_intermediation=False,
    revenue_linked_to_underlying_volume=False,
    company_reports_underlying_volume=False,
    evidence=PRIMARY,
)
check("R2-B marketing language alone is not a candidate", tri_b["candidate_marketplace"] is False)
check("R2-B SaaS keeps original module", res_b["final_module"] == "SOFTWARE")

# R2-C — principal-inventory retailer-like model stays original module.
tri_c = triage_marketplace(
    agency_or_net_presentation=True,
    capital_light_intermediation=False,
    intermediation_language=True,
)
res_c = classify_marketplace(
    original_module="GENERAL",
    candidate_marketplace=tri_c["candidate_marketplace"],
    two_sided_intermediation=True,
    revenue_linked_to_underlying_volume=False,
    company_reports_underlying_volume=True,
    evidence=PRIMARY,
)
check("R2-C principal economics not classified marketplace",
      res_c["final_module"] == "GENERAL" and res_c["reason_code"] == "DOCUMENTARY_TEST_NOT_MET")

# R2-D — agency/network economics with primary evidence routes correctly.
tri_d = triage_marketplace(
    agency_or_net_presentation=True,
    capital_light_intermediation=True,
    intermediation_language=False,
)
res_d = classify_marketplace(
    original_module="GENERAL",
    candidate_marketplace=tri_d["candidate_marketplace"],
    two_sided_intermediation=True,
    revenue_linked_to_underlying_volume=True,
    company_reports_underlying_volume=True,
    evidence=PRIMARY,
)
check("R2-D agency network routes marketplace",
      res_d["final_module"] == "MARKETPLACE_NETWORK")

# R2-E — incomplete documentary evidence preserves original module + provisional.
tri_e = triage_marketplace(
    agency_or_net_presentation=True,
    capital_light_intermediation=True,
    intermediation_language=None,
)
res_e = classify_marketplace(
    original_module="SOFTWARE",
    candidate_marketplace=tri_e["candidate_marketplace"],
    two_sided_intermediation=True,
    revenue_linked_to_underlying_volume=None,
    company_reports_underlying_volume=None,
    evidence=PRIMARY,
)
check("R2-E insufficient evidence does not force marketplace",
      res_e["final_module"] == "SOFTWARE" and res_e["classification_status"] == PROVISIONAL)

# Primary evidence is mandatory even if economics tests are both true.
secondary = Evidence(
    source_type="SECONDARY",
    source_url_or_accession="synthetic-secondary",
    filing_date="2026-01-01",
    classification_as_of="2026-01-01",
    evidence_excerpt_or_hash="synthetic-secondary-hash",
)
res_primary = classify_marketplace(
    original_module="GENERAL",
    candidate_marketplace=True,
    two_sided_intermediation=True,
    revenue_linked_to_underlying_volume=True,
    company_reports_underlying_volume=True,
    evidence=secondary,
)
check("R2 primary-source requirement",
      res_primary["final_module"] == "GENERAL"
      and res_primary["classification_status"] == PROVISIONAL
      and res_primary["reason_code"] == "PRIMARY_EVIDENCE_REQUIRED")

# R2-F — definition drift marks series conflicting.
series = [
    MetricPoint(100.0, "FY1", "GLOBAL", "volume-v1", "synthetic"),
    MetricPoint(120.0, "FY2", "GLOBAL", "volume-v2", "synthetic"),
]
drift = definition_drift_status(series)
check("R2-F definition drift -> CONFLICTING", drift["status"] == CONFLICTING)

# KPI normalization: same-period/scope ratios.
vol = MetricPoint(100.0, "FY", "GLOBAL", "gross_intermediated_volume", "synthetic")
revenue = MetricPoint(20.0, "FY", "GLOBAL", "net_revenue", "synthetic")
ebitda = MetricPoint(4.0, "FY", "GLOBAL", "ebitda", "synthetic")
fcf = MetricPoint(3.5, "FY", "GLOBAL", "fcf", "synthetic")
kpis = normalize_marketplace_kpis(
    underlying_volume=vol,
    net_revenue=revenue,
    ebitda=ebitda,
    fcf=fcf,
    retention_value=0.92,
    retention_kind="COHORT",
    retention_source="synthetic",
    frequency_growth=0.04,
    frequency_comparable=True,
    frequency_source="synthetic",
    unit_cost_decline=0.03,
    unit_cost_comparable=True,
    unit_cost_source="synthetic",
)
check("R2 normalized take rate", abs(kpis["take_rate"]["value"] - 0.20) < 1e-12)
check("R2 normalized EBITDA/volume", abs(kpis["ebitda_on_volume"]["value"] - 0.04) < 1e-12)
check("R2 normalized FCF/volume", abs(kpis["fcf_on_volume"]["value"] - 0.035) < 1e-12)
check("R2 cohort retention accepted", kpis["retention"]["status"] == PRESENT)

# Non-cohort retention is not approximated.
kpis_noncohort = normalize_marketplace_kpis(
    underlying_volume=vol,
    net_revenue=revenue,
    ebitda=ebitda,
    fcf=fcf,
    retention_value=0.95,
    retention_kind="AGGREGATE",
    retention_source="synthetic",
)
check("R2 non-cohort retention -> MISSING",
      kpis_noncohort["retention"]["status"] == MISSING)

# Scope mismatch is conflicting, not silently divided.
revenue_other_scope = MetricPoint(20.0, "FY", "REGION_A", "net_revenue", "synthetic")
ratio_bad = ratio_metric(revenue_other_scope, vol, field_name="take_rate")
check("R2 scope mismatch -> CONFLICTING", ratio_bad["status"] == CONFLICTING)

# Missing denominator is MISSING, never zero.
vol_missing = MetricPoint(None, "FY", "GLOBAL", "gross_intermediated_volume", "synthetic", status=MISSING)
ratio_missing = ratio_metric(revenue, vol_missing, field_name="take_rate")
check("R2 MISSING stays MISSING", ratio_missing["status"] == MISSING and ratio_missing["value"] is None)

# R3 — presentation invariance at the marketplace economics input layer.
# Two companies with identical volume economics but different reported accounting margins
# must feed identical marketplace scoring inputs.
gross_presentation = {
    "underlying_volume": 100.0,
    "ebitda_on_volume": 0.04,
    "fcf_on_volume": 0.035,
    "take_rate": 0.20,
    "cash_conversion": 0.95,
    "reported_op_margin": 0.04,
    "reported_fcf_margin": 0.035,
}
net_presentation = {
    **gross_presentation,
    "reported_op_margin": 0.20,
    "reported_fcf_margin": 0.175,
}
marketplace_scoring_keys = ("ebitda_on_volume", "fcf_on_volume", "take_rate", "cash_conversion")
check("R3 gross/net presentation does not alter marketplace scoring inputs",
      all(gross_presentation[k] == net_presentation[k] for k in marketplace_scoring_keys))
check("R3 accounting presentation can differ diagnostically",
      gross_presentation["reported_op_margin"] != net_presentation["reported_op_margin"])

# No routing based on a company identifier is accepted by the API.
sig = inspect.signature(classify_marketplace)
check("R2 classifier has no ticker/company-name parameter",
      "ticker" not in sig.parameters and "company" not in sig.parameters and "name" not in sig.parameters)

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)
print("R2/R3 SYNTHETIC SUITE PASSED")
