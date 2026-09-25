"""
Investment OS V4.2 — BR-09 marketplace/network classifier and KPI normalizer.

PRE-RANKING / SYNTHETIC-FIRST implementation.
No real ticker is referenced or hard-coded.
This module does not calculate BQS or IOS and does not promote a security
into any investment shortlist. It only:
  1) triages candidates for documentary review;
  2) classifies the economic model from primary documentary evidence;
  3) normalizes marketplace/network KPI with explicit provenance/status.

MISSING != 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Sequence

MISSING = "MISSING"
PRESENT = "PRESENT"
CONFLICTING = "CONFLICTING"
NOT_APPLICABLE = "NOT_APPLICABLE"
PROVISIONAL = "PROVISIONAL"
VERIFIED = "VERIFIED"

CLASSIFIER_VERSION = "V4.2-BR09-1.0"


@dataclass(frozen=True)
class Evidence:
    source_type: str
    source_url_or_accession: str
    filing_date: str
    classification_as_of: str
    evidence_excerpt_or_hash: str

    def is_primary(self) -> bool:
        return self.source_type.strip().upper() == "PRIMARY"

    def complete(self) -> bool:
        return all(
            isinstance(x, str) and bool(x.strip())
            for x in (
                self.source_type,
                self.source_url_or_accession,
                self.filing_date,
                self.classification_as_of,
                self.evidence_excerpt_or_hash,
            )
        )


@dataclass(frozen=True)
class MetricPoint:
    value: Optional[float]
    period: str
    scope: str
    definition: str
    source: str
    status: str = PRESENT

    def missing(self) -> bool:
        return self.status == MISSING or self.value is None


def triage_marketplace(
    *,
    agency_or_net_presentation: Optional[bool],
    capital_light_intermediation: Optional[bool],
    intermediation_language: Optional[bool],
) -> Dict[str, Any]:
    """Phase 0. >=2 positive general signals => documentary candidate.

    The function never assigns MARKETPLACE_NETWORK.
    Unknown signals (None) are not silently treated as positive.
    """
    signals = {
        "agency_or_net_presentation": agency_or_net_presentation,
        "capital_light_intermediation": capital_light_intermediation,
        "intermediation_language": intermediation_language,
    }
    positive = sorted(k for k, v in signals.items() if v is True)
    unknown = sorted(k for k, v in signals.items() if v is None)
    return {
        "candidate_marketplace": len(positive) >= 2,
        "positive_signal_count": len(positive),
        "positive_signals": positive,
        "unknown_signals": unknown,
        "assigned_module": None,
        "reason_code": "TRIAGE_ONLY",
        "classifier_version": CLASSIFIER_VERSION,
    }


def classify_marketplace(
    *,
    original_module: str,
    candidate_marketplace: bool,
    two_sided_intermediation: Optional[bool],
    revenue_linked_to_underlying_volume: Optional[bool],
    company_reports_underlying_volume: Optional[bool],
    evidence: Optional[Evidence],
) -> Dict[str, Any]:
    """Phase 1 documentary classification.

    MARKETPLACE_NETWORK requires BOTH defining economics to be YES and
    complete PRIMARY evidence. Otherwise the original module is preserved.
    """
    original_module = (original_module or "UNKNOWN").strip().upper()

    base = {
        "original_module": original_module,
        "candidate_marketplace": bool(candidate_marketplace),
        "two_sided_intermediation": two_sided_intermediation,
        "revenue_linked_to_underlying_volume": revenue_linked_to_underlying_volume,
        "company_reports_underlying_volume": company_reports_underlying_volume,
        "classifier_version": CLASSIFIER_VERSION,
    }

    if not candidate_marketplace:
        return {
            **base,
            "final_module": original_module,
            "classification_status": VERIFIED,
            "reason_code": "TRIAGE_NEGATIVE_KEEP_ORIGINAL",
        }

    required = (two_sided_intermediation, revenue_linked_to_underlying_volume)
    if any(v is None for v in required):
        return {
            **base,
            "final_module": original_module,
            "classification_status": PROVISIONAL,
            "reason_code": "INSUFFICIENT_DOCUMENTARY_EVIDENCE",
        }

    if not all(required):
        return {
            **base,
            "final_module": original_module,
            "classification_status": VERIFIED if evidence and evidence.complete() else PROVISIONAL,
            "reason_code": "DOCUMENTARY_TEST_NOT_MET",
        }

    if evidence is None or not evidence.complete() or not evidence.is_primary():
        return {
            **base,
            "final_module": original_module,
            "classification_status": PROVISIONAL,
            "reason_code": "PRIMARY_EVIDENCE_REQUIRED",
        }

    return {
        **base,
        "final_module": "MARKETPLACE_NETWORK",
        "classification_status": VERIFIED,
        "reason_code": "DOCUMENTARY_TEST_MET",
        "source_type": evidence.source_type,
        "source_url_or_accession": evidence.source_url_or_accession,
        "filing_date": evidence.filing_date,
        "classification_as_of": evidence.classification_as_of,
        "evidence_excerpt_or_hash": evidence.evidence_excerpt_or_hash,
    }


def _compatible(a: MetricPoint, b: MetricPoint) -> bool:
    return (
        a.period == b.period
        and a.scope == b.scope
        and bool(a.definition.strip())
        and bool(b.definition.strip())
    )


def ratio_metric(
    numerator: MetricPoint,
    denominator: MetricPoint,
    *,
    field_name: str,
) -> Dict[str, Any]:
    """Create a ratio only when both facts are present and scope-compatible."""
    if numerator.missing() or denominator.missing():
        return {
            "field": field_name,
            "value": None,
            "status": MISSING,
            "reason_code": "INPUT_MISSING",
        }
    if numerator.status == CONFLICTING or denominator.status == CONFLICTING:
        return {
            "field": field_name,
            "value": None,
            "status": CONFLICTING,
            "reason_code": "INPUT_CONFLICTING",
        }
    if not _compatible(numerator, denominator):
        return {
            "field": field_name,
            "value": None,
            "status": CONFLICTING,
            "reason_code": "PERIOD_OR_SCOPE_MISMATCH",
        }
    if denominator.value == 0:
        return {
            "field": field_name,
            "value": None,
            "status": CONFLICTING,
            "reason_code": "ZERO_DENOMINATOR",
        }
    return {
        "field": field_name,
        "value": numerator.value / denominator.value,
        "status": PRESENT,
        "period": numerator.period,
        "scope": numerator.scope,
        "numerator_source": numerator.source,
        "denominator_source": denominator.source,
        "classifier_version": CLASSIFIER_VERSION,
    }


def retention_metric(
    *,
    value: Optional[float],
    retention_kind: Optional[str],
    source: str,
) -> Dict[str, Any]:
    """Retention is accepted only if explicitly cohort-based (or equivalent)."""
    if value is None:
        return {"field": "retention", "value": None, "status": MISSING, "reason_code": "INPUT_MISSING"}
    kind = (retention_kind or "").strip().upper()
    if kind not in {"COHORT", "COHORT_EQUIVALENT"}:
        return {
            "field": "retention",
            "value": None,
            "status": MISSING,
            "reason_code": "NON_COHORT_RETENTION_NOT_ACCEPTED",
        }
    return {
        "field": "retention",
        "value": value,
        "status": PRESENT,
        "retention_kind": kind,
        "source": source,
        "classifier_version": CLASSIFIER_VERSION,
    }


def comparable_metric(
    *,
    field_name: str,
    value: Optional[float],
    comparable_over_time: Optional[bool],
    source: str,
) -> Dict[str, Any]:
    if value is None:
        return {"field": field_name, "value": None, "status": MISSING, "reason_code": "INPUT_MISSING"}
    if comparable_over_time is not True:
        return {
            "field": field_name,
            "value": None,
            "status": CONFLICTING if comparable_over_time is False else MISSING,
            "reason_code": "NOT_COMPARABLE_OVER_TIME" if comparable_over_time is False else "COMPARABILITY_UNKNOWN",
        }
    return {
        "field": field_name,
        "value": value,
        "status": PRESENT,
        "source": source,
        "classifier_version": CLASSIFIER_VERSION,
    }


def definition_drift_status(points: Sequence[MetricPoint]) -> Dict[str, Any]:
    """A changed company definition makes a time series CONFLICTING until reconciled."""
    present = [p for p in points if not p.missing()]
    if not present:
        return {"status": MISSING, "reason_code": "NO_PRESENT_POINTS"}
    definitions = {p.definition.strip() for p in present}
    scopes = {p.scope for p in present}
    if len(definitions) > 1 or len(scopes) > 1:
        return {"status": CONFLICTING, "reason_code": "DEFINITION_OR_SCOPE_DRIFT"}
    return {"status": PRESENT, "reason_code": "HOMOGENEOUS_SERIES"}


def normalize_marketplace_kpis(
    *,
    underlying_volume: MetricPoint,
    net_revenue: MetricPoint,
    ebitda: MetricPoint,
    fcf: MetricPoint,
    retention_value: Optional[float] = None,
    retention_kind: Optional[str] = None,
    retention_source: str = "",
    frequency_growth: Optional[float] = None,
    frequency_comparable: Optional[bool] = None,
    frequency_source: str = "",
    unit_cost_decline: Optional[float] = None,
    unit_cost_comparable: Optional[bool] = None,
    unit_cost_source: str = "",
) -> Dict[str, Any]:
    """Phase 3 normalizer. No undocumented proxy is generated."""
    return {
        "take_rate": ratio_metric(net_revenue, underlying_volume, field_name="take_rate"),
        "ebitda_on_volume": ratio_metric(ebitda, underlying_volume, field_name="ebitda_on_volume"),
        "fcf_on_volume": ratio_metric(fcf, underlying_volume, field_name="fcf_on_volume"),
        "retention": retention_metric(
            value=retention_value,
            retention_kind=retention_kind,
            source=retention_source,
        ),
        "frequency_growth": comparable_metric(
            field_name="frequency_growth",
            value=frequency_growth,
            comparable_over_time=frequency_comparable,
            source=frequency_source,
        ),
        "unit_cost_decline": comparable_metric(
            field_name="unit_cost_decline",
            value=unit_cost_decline,
            comparable_over_time=unit_cost_comparable,
            source=unit_cost_source,
        ),
    }
