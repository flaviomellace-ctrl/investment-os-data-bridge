from cash_quality_commitments_v42 import (
    CONFLICTING,
    MISSING,
    NOT_APPLICABLE,
    PRESENT,
    Commitment,
    ProvenancedAmount,
    cash_quality_diagnostic,
    commitments_diagnostic,
    leverage_stress_view,
    normalize_owner_earnings,
    reported_owner_earnings,
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

def pa(value, status=PRESENT, label="synthetic"):
    return ProvenancedAmount(
        value=value,
        status=status,
        source=f"{label}-source",
        data_as_of="2026-01-01",
        definition=f"{label}-definition",
    )

# R6-1 reported owner earnings requires all three inputs.
oe = reported_owner_earnings(100.0, 20.0, 10.0)
check("R6 reported OE = OCF-capex-SBC",
      oe["status"] == PRESENT and abs(oe["reported_owner_earnings"] - 70.0) < 1e-12)

oe_missing = reported_owner_earnings(100.0, 20.0, None)
check("R6 missing SBC is not zero",
      oe_missing["status"] == MISSING and oe_missing["reported_owner_earnings"] is None)

# R6-2 clean normalization.
norm_clean = normalize_owner_earnings(
    reported_oe=70.0,
    positive_temporary_cash_benefits=[],
    negative_temporary_cash_drags=[],
    normalization_complete=True,
)
check("R6 clean normalization preserves OE",
      norm_clean["status"] == PRESENT and norm_clean["normalized_owner_earnings"] == 70.0)
check("R6 clean normalization not material", norm_clean["material_adjustment"] is False)

# R6-3 reserve/float benefit is subtracted.
norm_reserve = normalize_owner_earnings(
    reported_oe=100.0,
    positive_temporary_cash_benefits=[pa(25.0, label="reserve-build")],
    negative_temporary_cash_drags=[],
    normalization_complete=True,
)
check("R6 temporary reserve/float cash benefit is removed",
      norm_reserve["normalized_owner_earnings"] == 75.0)
check("R6 25% adjustment is material",
      norm_reserve["material_adjustment"] is True)

diag_reserve = cash_quality_diagnostic(
    reported_oe=100.0,
    normalized_result=norm_reserve,
    reserve_or_float_dependency=True,
)
check("R6 material cash-quality adjustment -> PROVISIONAL",
      diag_reserve["ios_confidence_action"] == "PROVISIONAL")
check("R6 material cash-quality adjustment -> reconcile gate",
      diag_reserve["decision_gate_action"] == "RECONCILE_CASH_QUALITY")

# R6-4 temporary negative drag may be added back with provenance.
norm_drag = normalize_owner_earnings(
    reported_oe=80.0,
    positive_temporary_cash_benefits=[],
    negative_temporary_cash_drags=[pa(12.0, label="one-off-tax-catchup")],
    normalization_complete=True,
)
check("R6 documented temporary negative drag may be added back",
      norm_drag["normalized_owner_earnings"] == 92.0)

# R6-5 incomplete normalization cannot emit normalized OE.
norm_incomplete = normalize_owner_earnings(
    reported_oe=100.0,
    positive_temporary_cash_benefits=[pa(15.0)],
    negative_temporary_cash_drags=[],
    normalization_complete=False,
)
check("R6 incomplete normalization stays MISSING",
      norm_incomplete["status"] == MISSING
      and norm_incomplete["normalized_owner_earnings"] is None)

# R6-6 unprovenanced adjustment cannot be used.
bad = ProvenancedAmount(
    value=20.0,
    status=PRESENT,
    source="",
    data_as_of="2026-01-01",
    definition="temporary benefit",
)
norm_bad = normalize_owner_earnings(
    reported_oe=100.0,
    positive_temporary_cash_benefits=[bad],
    negative_temporary_cash_drags=[],
    normalization_complete=True,
)
check("R6 unprovenanced normalization input rejected",
      norm_bad["status"] == MISSING)

# R6-7 flags alone downgrade confidence even if amount cannot yet be normalized.
diag_wc = cash_quality_diagnostic(
    reported_oe=100.0,
    normalized_result={"status": MISSING, "normalized_owner_earnings": None},
    working_capital_anomaly=True,
)
check("R6 working-capital anomaly without full quantification -> PROVISIONAL",
      diag_wc["ios_confidence_action"] == "PROVISIONAL")

# R7 commitments.
quantified = Commitment(
    category="purchase_obligation",
    amount=60.0,
    status=PRESENT,
    material=True,
    already_in_debt=False,
    source="synthetic-primary",
    data_as_of="2026-01-01",
    definition="non-cancellable purchase obligation",
)
already_debt = Commitment(
    category="lease_already_in_debt",
    amount=40.0,
    status=PRESENT,
    material=True,
    already_in_debt=True,
    source="synthetic-primary",
    data_as_of="2026-01-01",
    definition="recognized lease liability",
)
unquantified_material = Commitment(
    category="fleet_offtake",
    amount=None,
    status=MISSING,
    material=True,
    already_in_debt=False,
    source="synthetic-primary",
    data_as_of="2026-01-01",
    definition="material off-take commitment, amount not disclosed",
)
unquantified_immaterial = Commitment(
    category="minor_service_contract",
    amount=None,
    status=MISSING,
    material=False,
    already_in_debt=False,
    source="synthetic-primary",
    data_as_of="2026-01-01",
    definition="immaterial service arrangement",
)

c1 = commitments_diagnostic([quantified, already_debt], owner_earnings=30.0)
check("R7 quantified uncovered commitment is summed",
      c1["quantified_uncovered_commitments"] == 60.0)
check("R7 already-in-debt commitment is not double counted",
      c1["excluded_already_in_debt"] == ["lease_already_in_debt"])
check("R7 quantified commitments alone do not auto-block",
      c1["decision_gate_action"] == "NO_AUTOMATIC_BLOCK")
check("R7 commitment/OE ratio is diagnostic",
      abs(c1["commitments_to_owner_earnings"] - 2.0) < 1e-12)

c2 = commitments_diagnostic([unquantified_material], owner_earnings=30.0)
check("R7 unquantified material commitment -> INVESTIGARE",
      c2["decision_gate_action"] == "INVESTIGARE")
check("R7 unquantified material commitment -> PROVISIONAL",
      c2["ios_confidence_action"] == "PROVISIONAL")

c3 = commitments_diagnostic([unquantified_immaterial], owner_earnings=30.0)
check("R7 immaterial unresolved commitment does not auto-block",
      c3["decision_gate_action"] == "NO_AUTOMATIC_BLOCK")

# R7 leverage stress secondary view.
lev = leverage_stress_view(
    gross_debt=300.0, cash=50.0, ebitda=120.0, sbc=20.0, module="GENERAL"
)
check("R7 gross debt/EBITDA computed", abs(lev["gross_debt_to_ebitda"] - 2.5) < 1e-12)
check("R7 net debt/EBITDA computed",
      abs(lev["net_debt_to_ebitda"] - (250.0/120.0)) < 1e-12)
check("R7 SBC-stress leverage computed",
      abs(lev["gross_debt_to_ebitda_after_sbc"] - 3.0) < 1e-12)
check("R7 SBC-stress at 3x -> CAUTION", lev["risk_band"] == "CAUTION")
check("R7 stress view remains explicitly secondary", lev["secondary_view_only"] is True)

lev_missing = leverage_stress_view(
    gross_debt=300.0, cash=50.0, ebitda=120.0, sbc=None, module="GENERAL"
)
check("R7 missing SBC does not become zero in leverage stress",
      lev_missing["status"] == MISSING)

lev_bank = leverage_stress_view(
    gross_debt=300.0, cash=50.0, ebitda=120.0, sbc=20.0, module="BANK"
)
check("R7 generic leverage stress is N/A for banks",
      lev_bank["status"] == NOT_APPLICABLE)

lev_bad = leverage_stress_view(
    gross_debt=300.0, cash=50.0, ebitda=10.0, sbc=15.0, module="GENERAL"
)
check("R7 nonpositive EBITDA-after-SBC is indeterminate, not fabricated",
      lev_bad["stress_metric_status"] == CONFLICTING
      and lev_bad["gross_debt_to_ebitda_after_sbc"] is None)

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)
print("R6/R7 SYNTHETIC SUITE PASSED")
