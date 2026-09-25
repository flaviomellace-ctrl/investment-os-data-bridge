"""
Investment OS V4.2 — Economic Inflection Lane (Lane I), synthetic-first freeze candidate.

This module is deliberately price-independent.
It does not calculate BQS or IOS and cannot emit BUY/ADD.
It exists only to rank economically inflecting businesses for qualitative review.

No real ticker is hard-coded or referenced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

LANE_I_VERSION = "V4.2-LANE-I-1.0"

MISSING = None
CONFLICTING = "CONFLICTING"

# Frozen pre-real-data eligibility policy.
MIN_BQS = 60.0
MIN_REVENUE_CAGR3 = 0.05
MIN_FCF_CAGR3 = 0.15
MIN_FCF_PER_SHARE_CAGR3 = 0.12
MIN_CASH_CONVERSION = 0.75
MAX_SHARE_CHANGE = 0.03

# Lane capacity frozen before any real-data V4.2 ranking.
DEEP_DIVE_TOTAL = 10
LANE_V_QUOTA = 7
LANE_I_QUOTA = 3


def _num(v: Any) -> Optional[float]:
    if v in (None, "", "MISSING", CONFLICTING):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if not math_isfinite(f) else f


def math_isfinite(v: float) -> bool:
    return v == v and v not in (float("inf"), float("-inf"))


def _scale(v: float, lo: float, hi: float, points: float) -> float:
    if hi <= lo:
        raise ValueError("invalid scale")
    t = (v - lo) / (hi - lo)
    return max(0.0, min(1.0, t)) * points


def baseline_growth_v41(revenue_cagr3: Optional[float]) -> Optional[float]:
    """Observed V4.1 expected-return growth contribution."""
    r = _num(revenue_cagr3)
    if r is None:
        return None
    return max(0.0, min(r, 0.10))


def blended_growth_candidate(
    revenue_cagr3: Optional[float],
    fcf_cagr3: Optional[float],
    fcf_per_share_cagr3: Optional[float],
) -> Optional[float]:
    """Candidate A: weighted blended trajectory, capped at 15%.

    Included for the bake-off; not automatically authorized for production.
    """
    vals = [_num(revenue_cagr3), _num(fcf_cagr3), _num(fcf_per_share_cagr3)]
    if any(v is None for v in vals):
        return None
    r, f, fps = vals
    r = max(0.0, min(r, 0.25))
    f = max(0.0, min(f, 0.25))
    fps = max(0.0, min(fps, 0.25))
    return min(0.15, 0.40 * r + 0.30 * f + 0.30 * fps)


def guarded_per_share_growth_candidate(
    revenue_cagr3: Optional[float],
    fcf_per_share_cagr3: Optional[float],
) -> Optional[float]:
    """Candidate B: growth recognized only when sales and per-share cash agree.

    g = min(max(revenue CAGR, 0), max(FCF/share CAGR, 0), 15%)

    This is conservative by construction:
    - no credit for cash growth without revenue support;
    - no credit for revenue growth without per-share cash support;
    - dilution is naturally reflected in FCF/share;
    - the maximum recognized growth is 15%.
    """
    r = _num(revenue_cagr3)
    fps = _num(fcf_per_share_cagr3)
    if r is None or fps is None:
        return None
    return min(max(r, 0.0), max(fps, 0.0), 0.15)


def growth_bakeoff(
    *,
    revenue_cagr3: Optional[float],
    fcf_cagr3: Optional[float],
    fcf_per_share_cagr3: Optional[float],
) -> Dict[str, Optional[float]]:
    return {
        "G0_V41_BASELINE": baseline_growth_v41(revenue_cagr3),
        "G1_BLENDED": blended_growth_candidate(
            revenue_cagr3, fcf_cagr3, fcf_per_share_cagr3
        ),
        "G2_GUARDED_PER_SHARE": guarded_per_share_growth_candidate(
            revenue_cagr3, fcf_per_share_cagr3
        ),
    }


def inflection_assessment(c: Dict[str, Any]) -> Dict[str, Any]:
    """Assess a company for Lane I without using price.

    Eligibility is an economic floor, not a BUY signal.
    Flagged candidates can be recorded but are not HIGH_CONFIDENCE Lane-I selections.
    """
    bqs = _num(c.get("bqs"))
    owner = _num(c.get("owner_earnings"))
    rev = _num(c.get("revenue_cagr3"))
    fcf = _num(c.get("fcf_cagr3"))
    fps = _num(c.get("fcf_per_share_cagr3"))
    conv = _num(c.get("cash_conversion"))
    sh = _num(c.get("share_change"))

    missing = [
        name for name, value in (
            ("bqs", bqs),
            ("owner_earnings", owner),
            ("revenue_cagr3", rev),
            ("fcf_cagr3", fcf),
            ("fcf_per_share_cagr3", fps),
            ("cash_conversion", conv),
            ("share_change", sh),
        ) if value is None
    ]
    if missing:
        return {
            "eligible": False,
            "high_confidence": False,
            "score": None,
            "confidence": "NOT_CALCULATED",
            "reason_code": "REQUIRED_INPUT_MISSING",
            "missing": missing,
            "version": LANE_I_VERSION,
        }

    reasons = []
    if bqs < MIN_BQS:
        reasons.append("BQS_BELOW_60")
    if owner <= 0:
        reasons.append("OWNER_EARNINGS_NOT_POSITIVE")
    if rev < MIN_REVENUE_CAGR3:
        reasons.append("REVENUE_CAGR_BELOW_FLOOR")
    if fcf < MIN_FCF_CAGR3:
        reasons.append("FCF_CAGR_BELOW_FLOOR")
    if fps < MIN_FCF_PER_SHARE_CAGR3:
        reasons.append("FCF_PER_SHARE_CAGR_BELOW_FLOOR")
    if conv < MIN_CASH_CONVERSION:
        reasons.append("CASH_CONVERSION_BELOW_FLOOR")
    if sh > MAX_SHARE_CHANGE:
        reasons.append("DILUTION_ABOVE_LIMIT")

    eligible = not reasons

    score = (
        _scale(rev, 0.05, 0.20, 25.0)
        + _scale(fcf, 0.15, 0.35, 30.0)
        + _scale(fps, 0.12, 0.30, 30.0)
        + _scale(conv, 0.75, 1.10, 10.0)
        + _scale(-sh, -0.03, 0.02, 5.0)
    )

    growth_flags = tuple(c.get("growth_flags") or ())
    quality_flags = tuple(c.get("quality_flags") or ())
    cyclical_flag = bool(c.get("cyclical_rebound_flag", False))
    flags = tuple(sorted(set(growth_flags + quality_flags + (("CYCLICAL_REBOUND",) if cyclical_flag else ()))))

    high_confidence = eligible and not flags
    confidence = (
        "HIGH_CONFIDENCE"
        if high_confidence
        else ("PROVISIONAL" if eligible else "NOT_ELIGIBLE")
    )

    return {
        "eligible": eligible,
        "high_confidence": high_confidence,
        "score": round(score, 3),
        "confidence": confidence,
        "reason_code": "ELIGIBLE" if eligible else "ELIGIBILITY_FLOOR_NOT_MET",
        "reasons": reasons,
        "flags": list(flags),
        "version": LANE_I_VERSION,
    }


def rank_lane_i(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank only HIGH_CONFIDENCE Lane-I candidates.

    Tie-breaks are frozen before real-data ranking:
    inflection score DESC, BQS DESC, FCF/share CAGR DESC, entity_key ASC.
    """
    enriched = []
    for row in rows:
        assessment = inflection_assessment(row)
        if not assessment["high_confidence"]:
            continue
        enriched.append({**row, **assessment})

    return sorted(
        enriched,
        key=lambda r: (
            -float(r["score"]),
            -float(r["bqs"]),
            -float(r["fcf_per_share_cagr3"]),
            str(r.get("entity_key", "")),
        ),
    )


def merge_deep_dive_queue(
    lane_v: Sequence[Dict[str, Any]],
    lane_i: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Frozen 7+3 merge policy, with deterministic dedupe/backfill.

    1) take first 7 from valuation lane;
    2) add first 3 high-confidence inflection names not already selected;
    3) if fewer than 3 are available, backfill from valuation lane from rank 8 onward;
    4) total <= 10.
    """
    selected: List[Dict[str, Any]] = []
    seen = set()

    def key(row: Dict[str, Any]) -> str:
        return str(row["entity_key"])

    for row in lane_v:
        if len(selected) >= LANE_V_QUOTA:
            break
        k = key(row)
        if k not in seen:
            selected.append({**row, "selection_lane": "V"})
            seen.add(k)

    i_added = 0
    for row in lane_i:
        if i_added >= LANE_I_QUOTA:
            break
        k = key(row)
        if k not in seen:
            selected.append({**row, "selection_lane": "I"})
            seen.add(k)
            i_added += 1

    if len(selected) < DEEP_DIVE_TOTAL:
        for row in lane_v[LANE_V_QUOTA:]:
            if len(selected) >= DEEP_DIVE_TOTAL:
                break
            k = key(row)
            if k not in seen:
                selected.append({**row, "selection_lane": "V_BACKFILL"})
                seen.add(k)

    return selected[:DEEP_DIVE_TOTAL]
