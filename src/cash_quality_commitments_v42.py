"""
Investment OS V4.2 — R6/R7 quality-of-cash, commitments, and leverage-stress diagnostics.

Synthetic-first, pre-real-data implementation.

This module:
- does NOT calculate BQS;
- does NOT change IOS weights;
- does NOT emit BUY/ADD;
- never converts MISSING to zero;
- produces diagnostics, confidence downgrades, and Decision-Gate review flags only.

No real ticker is referenced or hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence
import math

MODULE_VERSION = "V4.2-R6R7-1.0"

PRESENT = "PRESENT"
MISSING = "MISSING"
CONFLICTING = "CONFLICTING"
NOT_APPLICABLE = "NOT_APPLICABLE"

# General pre-real-data materiality rule:
# a documented normalization adjustment >=10% of reported owner earnings is material.
MATERIAL_ADJUSTMENT_RATIO = 0.10

# Secondary leverage-stress interpretation only; it does not replace V4.1 leverage thresholds.
LEVERAGE_STRESS_CAUTION = 3.0
LEVERAGE_STRESS_HIGH = 4.0


@dataclass(frozen=True)
class ProvenancedAmount:
    value: Optional[float]
    status: str
    source: str
    data_as_of: str
    definition: str

    def usable(self) -> bool:
        return (
            self.status == PRESENT
            and self.value is not None
            and bool(self.source.strip())
            and bool(self.data_as_of.strip())
            and bool(self.definition.strip())
        )


@dataclass(frozen=True)
class Commitment:
    category: str
    amount: Optional[float]
    status: str
    material: bool
    already_in_debt: bool
    source: str
    data_as_of: str
    definition: str

    def quantified(self) -> bool:
        return (
            self.status == PRESENT
            and self.amount is not None
            and self.amount >= 0
            and bool(self.source.strip())
            and bool(self.data_as_of.strip())
            and bool(self.definition.strip())
        )


def _finite(v: Any) -> Optional[float]:
    if v is None or v in (MISSING, CONFLICTING, ""):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def reported_owner_earnings(
    ocf: Optional[float],
    capex: Optional[float],
    sbc: Optional[float],
) -> Dict[str, Any]:
    """Prudential owner earnings = OCF - capex - SBC.

    All three inputs are required. Missing SBC is never treated as zero.
    """
    vals = [_finite(ocf), _finite(capex), _finite(sbc)]
    if any(v is None for v in vals):
        return {
            "status": MISSING,
            "reported_owner_earnings": None,
            "reason_code": "OCF_CAPEX_OR_SBC_MISSING",
            "version": MODULE_VERSION,
        }
    o, c, s = vals
    return {
        "status": PRESENT,
        "reported_owner_earnings": o - c - s,
        "reason_code": "CALCULATED_FROM_REPORTED_INPUTS",
        "version": MODULE_VERSION,
    }


def normalize_owner_earnings(
    *,
    reported_oe: Optional[float],
    positive_temporary_cash_benefits: Sequence[ProvenancedAmount],
    negative_temporary_cash_drags: Sequence[ProvenancedAmount],
    normalization_complete: bool,
) -> Dict[str, Any]:
    """Normalize reported owner earnings only with explicit provenance.

    Positive temporary benefits are subtracted.
    Negative temporary drags are added back.

    Examples of positive temporary benefits:
    - reserve/float build that temporarily boosts OCF;
    - tax timing benefit;
    - unusual working-capital release.

    Examples of negative temporary drags:
    - unusual tax catch-up;
    - unusual working-capital build.

    `normalization_complete=False` means the diagnostic may list known adjustments
    but must NOT emit normalized_owner_earnings.
    """
    roe = _finite(reported_oe)
    if roe is None:
        return {
            "status": MISSING,
            "normalized_owner_earnings": None,
            "reason_code": "REPORTED_OWNER_EARNINGS_MISSING",
            "version": MODULE_VERSION,
        }

    all_items = list(positive_temporary_cash_benefits) + list(negative_temporary_cash_drags)
    unusable = [x for x in all_items if not x.usable()]
    if unusable:
        return {
            "status": MISSING,
            "normalized_owner_earnings": None,
            "reason_code": "NORMALIZATION_INPUT_MISSING_OR_UNPROVENANCED",
            "unusable_count": len(unusable),
            "version": MODULE_VERSION,
        }

    positive = sum(float(x.value) for x in positive_temporary_cash_benefits)
    negative = sum(float(x.value) for x in negative_temporary_cash_drags)
    net_adjustment = -positive + negative

    if not normalization_complete:
        return {
            "status": MISSING,
            "normalized_owner_earnings": None,
            "known_net_adjustment": net_adjustment,
            "reason_code": "NORMALIZATION_NOT_COMPLETE",
            "version": MODULE_VERSION,
        }

    normalized = roe + net_adjustment
    ratio = abs(net_adjustment) / abs(roe) if roe != 0 else None
    material = ratio is None or ratio >= MATERIAL_ADJUSTMENT_RATIO

    return {
        "status": PRESENT,
        "normalized_owner_earnings": normalized,
        "net_adjustment": net_adjustment,
        "adjustment_ratio": ratio,
        "material_adjustment": material,
        "reason_code": "NORMALIZED_WITH_PROVENANCE",
        "version": MODULE_VERSION,
    }


def cash_quality_diagnostic(
    *,
    reported_oe: Optional[float],
    normalized_result: Dict[str, Any],
    working_capital_anomaly: bool = False,
    reserve_or_float_dependency: bool = False,
    tax_timing_anomaly: bool = False,
    noncash_revaluation_flag: bool = False,
) -> Dict[str, Any]:
    """Return confidence/gate diagnostics. Does not alter IOS numerically."""
    flags: List[str] = []
    if working_capital_anomaly:
        flags.append("WORKING_CAPITAL_ANOMALY")
    if reserve_or_float_dependency:
        flags.append("RESERVE_OR_FLOAT_DEPENDENCY")
    if tax_timing_anomaly:
        flags.append("TAX_TIMING_ANOMALY")
    if noncash_revaluation_flag:
        flags.append("NONCASH_REVALUATION")

    normalized_status = normalized_result.get("status")
    material_adjustment = bool(normalized_result.get("material_adjustment", False))

    if normalized_status != PRESENT and flags:
        confidence = "PROVISIONAL"
        gate = "RECONCILE_CASH_QUALITY"
    elif material_adjustment or flags:
        confidence = "PROVISIONAL"
        gate = "RECONCILE_CASH_QUALITY"
    else:
        confidence = "UNCHANGED"
        gate = "NO_ADDITIONAL_CASH_QUALITY_BLOCK"

    return {
        "cash_quality_flags": sorted(flags),
        "ios_confidence_action": confidence,
        "decision_gate_action": gate,
        "material_adjustment": material_adjustment,
        "version": MODULE_VERSION,
    }


def commitments_diagnostic(
    commitments: Sequence[Commitment],
    *,
    owner_earnings: Optional[float] = None,
) -> Dict[str, Any]:
    """Assess fixed claims not already captured in debt.

    Missing or unquantified material commitments force INVESTIGARE.
    Quantified obligations are reported, not silently capitalized into IOS.
    """
    unresolved_material: List[str] = []
    included: List[Commitment] = []
    excluded_as_debt: List[str] = []
    immaterial_unresolved: List[str] = []

    for item in commitments:
        if item.already_in_debt:
            excluded_as_debt.append(item.category)
            continue

        if item.quantified():
            included.append(item)
            continue

        if item.material:
            unresolved_material.append(item.category)
        else:
            immaterial_unresolved.append(item.category)

    quantified_total = sum(float(x.amount) for x in included)
    oe = _finite(owner_earnings)
    ratio = None
    if oe is not None and oe > 0:
        ratio = quantified_total / oe

    if unresolved_material:
        gate = "INVESTIGARE"
        confidence = "PROVISIONAL"
        reason = "MATERIAL_COMMITMENT_UNQUANTIFIED_OR_MISSING"
    else:
        gate = "NO_AUTOMATIC_BLOCK"
        confidence = "UNCHANGED"
        reason = "NO_UNRESOLVED_MATERIAL_COMMITMENT"

    return {
        "quantified_uncovered_commitments": quantified_total,
        "commitments_to_owner_earnings": ratio,
        "unresolved_material_categories": sorted(unresolved_material),
        "excluded_already_in_debt": sorted(excluded_as_debt),
        "immaterial_unresolved_categories": sorted(immaterial_unresolved),
        "ios_confidence_action": confidence,
        "decision_gate_action": gate,
        "reason_code": reason,
        "version": MODULE_VERSION,
    }


def leverage_stress_view(
    *,
    gross_debt: Optional[float],
    cash: Optional[float],
    ebitda: Optional[float],
    sbc: Optional[float],
    module: str = "GENERAL",
) -> Dict[str, Any]:
    """Secondary leverage view; not valid for BANK/INSURANCE.

    Reports debt/EBITDA and debt/(EBITDA-SBC). It does not replace
    the primary leverage metric or any existing V4.1 threshold.
    """
    mod = (module or "GENERAL").strip().upper()
    if mod in {"BANK", "INSURANCE"}:
        return {
            "status": NOT_APPLICABLE,
            "reason_code": "MODULE_REQUIRES_SECTOR_SPECIFIC_CAPITAL_METRICS",
            "version": MODULE_VERSION,
        }

    vals = [_finite(gross_debt), _finite(cash), _finite(ebitda), _finite(sbc)]
    if any(v is None for v in vals):
        return {
            "status": MISSING,
            "reason_code": "LEVERAGE_INPUT_MISSING",
            "version": MODULE_VERSION,
        }

    debt, csh, ebit, stock_comp = vals
    net_debt = debt - csh

    if ebit <= 0:
        return {
            "status": CONFLICTING,
            "reason_code": "NONPOSITIVE_EBITDA",
            "version": MODULE_VERSION,
        }

    ebitda_after_sbc = ebit - stock_comp
    gross_ratio = debt / ebit
    net_ratio = net_debt / ebit

    if ebitda_after_sbc <= 0:
        stress_ratio = None
        stress_status = CONFLICTING
    else:
        stress_ratio = debt / ebitda_after_sbc
        stress_status = PRESENT

    if stress_ratio is None:
        risk_band = "INDETERMINATE"
    elif stress_ratio >= LEVERAGE_STRESS_HIGH:
        risk_band = "HIGH"
    elif stress_ratio >= LEVERAGE_STRESS_CAUTION:
        risk_band = "CAUTION"
    else:
        risk_band = "BELOW_CAUTION"

    return {
        "status": PRESENT,
        "gross_debt_to_ebitda": gross_ratio,
        "net_debt_to_ebitda": net_ratio,
        "gross_debt_to_ebitda_after_sbc": stress_ratio,
        "stress_metric_status": stress_status,
        "risk_band": risk_band,
        "secondary_view_only": True,
        "version": MODULE_VERSION,
    }
