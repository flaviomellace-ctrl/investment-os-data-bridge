#!/usr/bin/env python3
"""Investment OS V4.2 - integrated pipeline orchestrator (research / validation only).

Composes, WITHOUT modifying them, the frozen components:
  engine (BQS/IOS/can_emit_buy) -> SIC adapter -> BR-09 classifier -> Lane V / Lane I
  -> 7+3 deep-dive queue -> cash-quality / commitments / leverage overlays -> Decision Gate.

This file contains no scoring formula, weight or threshold of its own. Every numeric
policy is read from the hash-pinned frozen modules. The two BR-09 Phase-0 accounting
thresholds are the values frozen in src/r10d_real_overlays.py (R10D) and are verified
against that file by tests/test_v42_integrated_pipeline.py.

Hard properties:
- no network access, no clock, no randomness: same inputs => byte-identical output;
- no entity identifier is referenced or special-cased;
- absent documentary evidence is never read as "no anomaly": it is NOT_REVIEWED and blocks;
- buy_add_allowed is always False (system NOT LIVE). The engine gate is additionally
  evaluated under a hypothetical live state purely as a diagnostic for control testing.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PIPELINE_VERSION = "V4.2-INTEGRATED-1.1"
OUTPUT_SCHEMA = "investment_os_v4_2_integrated_run_v1"
EVIDENCE_SCHEMA = "v42_integrated_evidence_v1"

SRC = Path(__file__).resolve().parent
FROZEN_COMPONENTS = {
    "engine": ("investment_os/v4_2/v4_scoring.py", "cbdb4e24173638d8377422f13094020090b2253fa1566a7e06374da32348ed6e"),
    "adapter": ("br04_data09_preflight.py", "aa75f344a658e3c8057c837b2451f2509097f9fa104887fed51159e55a867ad8"),
    "classifier": ("marketplace_classifier_v42.py", "c4031e77f9baf8347b7c07f82decb8bf0e6b2209bae3d9f21c06c7a61b92d170"),
    "lane": ("inflection_lane_v42.py", "c45dbb85558919358a727c0dbe3d657d9cd9a41ea6987a51289374af69b55c3a"),
    "cash": ("cash_quality_commitments_v42.py", "1d76a9a260793614edb5964b02eaed71b8b0ce6307fdb257d16773b9adb1ef3a"),
}
# BR-09 Phase-0 thresholds frozen in R10D before the first real-text scan (not new policy).
MAX_COGS_TO_REVENUE = 0.35
MAX_CAPEX_TO_REVENUE = 0.05
MIXED_BASIS_SUFFIX = "MIXED_CONTINUING_DISCONTINUED_BASIS"
MARKETPLACE = "MARKETPLACE_NETWORK"


class IntegrationError(RuntimeError):
    pass


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_components(src: Path = SRC) -> Dict[str, Any]:
    """Load each frozen module by path after verifying its SHA-256 pin."""
    out: Dict[str, Any] = {}
    for name, (rel, pin) in FROZEN_COMPONENTS.items():
        path = src / rel
        actual = sha256_bytes(path.read_bytes())
        if actual != pin:
            raise IntegrationError(f"frozen component hash mismatch: {name} {actual} != {pin}")
        spec = importlib.util.spec_from_file_location(f"v42_frozen_{name}", path)
        if spec is None or spec.loader is None:
            raise IntegrationError(f"cannot load {name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        out[name] = module
    return out


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    text = str(value).strip()
    if text in ("", "nan", "None", "MISSING", "NA", "NOT_APPLICABLE", "CONFLICTING"):
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _tri(value: Any, label: str) -> Optional[bool]:
    if value is None or isinstance(value, bool):
        return value
    raise IntegrationError(f"{label} must be true, false or null")


def _strict_bool(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    raise IntegrationError(f"{label} must be a strict boolean")


def _point(market, spec: Optional[dict]):
    if not spec:
        return market.MetricPoint(None, "", "", "", "", market.MISSING)
    return market.MetricPoint(_num(spec.get("value")), str(spec.get("period", "")), str(spec.get("scope", "")),
                              str(spec.get("definition", "")), str(spec.get("source", "")),
                              str(spec.get("status", market.PRESENT)))


def restore_growth_guard_inputs(c: dict, row: dict) -> None:
    """Supply the two inputs read by the engine's own normalize_growth() guard.

    The recovered SIC adapter omits them, which silently disables BASE_EFFECT_SUSPECTED and
    PRIOR_YEAR_ONE_OFF_SUSPECTED. Definitions are those of the original V4.1 quantitative-freeze
    adapter (run 36045268572). They feed flags only: no BQS/IOS number depends on them.
    """
    cur, prior = _num(row.get("annual_operating_income")), _num(row.get("prior_operating_income"))
    c["opinc_yoy"] = None if cur is None or prior in (None, 0) else cur / prior - 1.0
    c["net_income_series"] = [_num(row.get(k)) for k in ("fy_minus_3_net_income", "fy_minus_2_net_income",
                                                         "fy_minus_1_net_income", "annual_net_income")]


def open_conflicts(ev: dict) -> List[str]:
    """Fields for which a primary-source reconciliation found an unresolved difference with the candidate."""
    out = []
    for item in ev.get("data_conflicts") or []:
        if not str(item.get("field", "")).strip() or not str(item.get("source", "")).strip():
            raise IntegrationError("data conflict needs field and source")
        if item.get("status", "OPEN") != "RESOLVED":
            out.append(str(item["field"]))
    return sorted(out)


def classify_entity(row: dict, original_module: str, br09: Optional[dict], market) -> Dict[str, Any]:
    """BR-09 Phase 0 + Phase 1 + KPI normalisation from supplied documentary evidence."""
    if br09 is None:
        # Plan R2 case 5 / contract par. 4: insufficient evidence => original module + PROVISIONAL.
        return dict(reviewed=False, final_module=original_module, classification_status=market.PROVISIONAL,
                    reason_code="NO_DOCUMENTARY_EVIDENCE_SUPPLIED", candidate_marketplace=None,
                    kpis={}, kpi_status={}, kpi_conflict=False)
    revenue, capex = _num(row.get("annual_revenue")), _num(row.get("annual_capex"))
    cogs = _num((br09.get("cogs") or {}).get("value"))
    capital_light: Optional[bool] = None
    if cogs is not None and capex is not None and revenue not in (None, 0):
        capital_light = (cogs / revenue <= MAX_COGS_TO_REVENUE) and (abs(capex) / revenue <= MAX_CAPEX_TO_REVENUE)
    triage = market.triage_marketplace(
        agency_or_net_presentation=_tri(br09.get("agency_or_net_presentation"), "agency_or_net_presentation"),
        capital_light_intermediation=capital_light,
        intermediation_language=_tri(br09.get("intermediation_language"), "intermediation_language"))
    ev = br09.get("evidence")
    evidence = None if not ev else market.Evidence(
        source_type=str(ev.get("source_type", "")), source_url_or_accession=str(ev.get("source_url_or_accession", "")),
        filing_date=str(ev.get("filing_date", "")), classification_as_of=str(ev.get("classification_as_of", "")),
        evidence_excerpt_or_hash=str(ev.get("evidence_excerpt_or_hash", "")))
    result = market.classify_marketplace(
        original_module=original_module, candidate_marketplace=triage["candidate_marketplace"],
        two_sided_intermediation=_tri(br09.get("two_sided_intermediation"), "two_sided_intermediation"),
        revenue_linked_to_underlying_volume=_tri(br09.get("revenue_linked_to_underlying_volume"), "revenue_linked_to_underlying_volume"),
        company_reports_underlying_volume=_tri(br09.get("company_reports_underlying_volume"), "company_reports_underlying_volume"),
        evidence=evidence)
    if not triage["candidate_marketplace"] and triage["positive_signal_count"] + len(triage["unknown_signals"]) >= 2:
        # A negative triage that the unknown signals could still overturn is not a documented negative.
        result = dict(result, classification_status=market.PROVISIONAL, reason_code="TRIAGE_SIGNALS_UNKNOWN")
    kpis: Dict[str, Optional[float]] = {}
    status: Dict[str, str] = {}
    if result["final_module"] == MARKETPLACE and result["classification_status"] == market.VERIFIED:
        k = br09.get("kpis") or {}
        ret, freq, unit, two = (k.get(n) or {} for n in ("retention", "frequency_growth", "unit_cost_decline", "two_sided_growth"))
        norm = market.normalize_marketplace_kpis(
            underlying_volume=_point(market, k.get("underlying_volume")), net_revenue=_point(market, k.get("net_revenue")),
            ebitda=_point(market, k.get("ebitda")), fcf=_point(market, k.get("fcf")),
            retention_value=_num(ret.get("value")), retention_kind=ret.get("kind"), retention_source=str(ret.get("source", "")),
            frequency_growth=_num(freq.get("value")), frequency_comparable=_tri(freq.get("comparable"), "frequency comparable"),
            frequency_source=str(freq.get("source", "")),
            unit_cost_decline=_num(unit.get("value")), unit_cost_comparable=_tri(unit.get("comparable"), "unit cost comparable"),
            unit_cost_source=str(unit.get("source", "")))
        norm["two_sided_growth"] = market.comparable_metric(
            field_name="two_sided_growth", value=_num(two.get("value")),
            comparable_over_time=_tri(two.get("comparable"), "two-sided comparable"), source=str(two.get("source", "")))
        for name, item in sorted(norm.items()):
            status[name] = item["status"]
            kpis[name] = item["value"] if item["status"] == market.PRESENT else None
    return dict(reviewed=True, final_module=result["final_module"], classification_status=result["classification_status"],
                reason_code=result["reason_code"], candidate_marketplace=triage["candidate_marketplace"],
                positive_signals=triage["positive_signals"], unknown_signals=triage["unknown_signals"],
                capital_light_signal=capital_light, kpis=kpis, kpi_status=status,
                kpi_conflict=any(v == market.CONFLICTING for v in status.values()))


def _amounts(cash, items) -> list:
    return [cash.ProvenancedAmount(_num(x.get("value")), str(x.get("status", cash.PRESENT)), str(x.get("source", "")),
                                   str(x.get("data_as_of", "")), str(x.get("definition", ""))) for x in (items or [])]


def overlay_entity(row: dict, module: str, ev: dict, cash) -> Dict[str, Any]:
    """R6/R7 cash-quality, commitments and secondary leverage view for one queue entity."""
    ocf, capex, sbc = (_num(row.get(k)) for k in ("annual_operating_cash_flow", "annual_capex", "annual_sbc"))
    owner = cash.reported_owner_earnings(ocf, capex, sbc)
    reported = owner.get("reported_owner_earnings")
    out: Dict[str, Any] = dict(reported_owner_earnings=reported, owner_earnings_status=owner["status"])
    cq = ev.get("cash_quality")
    if cq is None:
        out.update(cash_quality_reviewed=False, cash_quality_gate="NOT_REVIEWED_EVIDENCE_MISSING", cash_quality_flags=[],
                   normalized_owner_earnings=None, normalization_reason="NOT_REVIEWED")
    else:
        norm = cash.normalize_owner_earnings(
            reported_oe=reported, positive_temporary_cash_benefits=_amounts(cash, cq.get("positive_temporary_cash_benefits")),
            negative_temporary_cash_drags=_amounts(cash, cq.get("negative_temporary_cash_drags")),
            normalization_complete=_strict_bool(cq.get("normalization_complete", False), "normalization_complete"))
        diag = cash.cash_quality_diagnostic(
            reported_oe=reported, normalized_result=norm,
            **{k: _strict_bool(cq.get(k, False), k) for k in ("working_capital_anomaly", "reserve_or_float_dependency",
                                                             "tax_timing_anomaly", "noncash_revaluation_flag")})
        out.update(cash_quality_reviewed=True, cash_quality_gate=diag["decision_gate_action"],
                   cash_quality_flags=diag["cash_quality_flags"], normalized_owner_earnings=norm.get("normalized_owner_earnings"),
                   normalization_reason=norm["reason_code"])
    cm = ev.get("commitments")
    if cm is None:
        out.update(commitments_reviewed=False, commitments_gate="NOT_REVIEWED_EVIDENCE_MISSING",
                   unresolved_material_commitments=[], quantified_uncovered_commitments=None, commitment_inventory_complete=False)
    else:
        items = []
        lease = _num(row.get("operating_lease_liabilities"))
        if lease is not None:
            items.append(cash.Commitment("OPERATING_LEASE_LIABILITY", lease, cash.PRESENT, False, False,
                                         "candidate:operating_lease_liabilities", str(row.get("annual_period", "") or "candidate"),
                                         "reported operating lease liability"))
        supplied = {str(x.get("category", "")) for x in cm.get("items") or []}
        if lease is None and "OPERATING_LEASE_LIABILITY" not in supplied:
            # Decision D3 (approved 2026-11-11): a missing lease liability is an unquantified material commitment, never zero.
            items.append(cash.Commitment("OPERATING_LEASE_LIABILITY", None, cash.MISSING, True, False,
                                         "candidate:operating_lease_liabilities", "", "operating lease liability not available"))
        for x in cm.get("items") or []:
            items.append(cash.Commitment(str(x.get("category", "")), _num(x.get("amount")), str(x.get("status", cash.MISSING)),
                                         _strict_bool(x.get("material", True), "material"),
                                         _strict_bool(x.get("already_in_debt", False), "already_in_debt"),
                                         str(x.get("source", "")), str(x.get("data_as_of", "")), str(x.get("definition", ""))))
        diag = cash.commitments_diagnostic(items, owner_earnings=reported)
        out.update(commitments_reviewed=True, commitments_gate=diag["decision_gate_action"],
                   unresolved_material_commitments=diag["unresolved_material_categories"],
                   quantified_uncovered_commitments=diag["quantified_uncovered_commitments"],
                   excluded_already_in_debt=diag["excluded_already_in_debt"],
                   commitment_inventory_complete=_strict_bool(cm.get("inventory_complete", False), "inventory_complete"))
    da = _num(((ev.get("leverage") or {}).get("depreciation_amortization") or {}).get("value"))
    opinc = _num(row.get("annual_operating_income"))
    lev = cash.leverage_stress_view(gross_debt=_num(row.get("total_debt")), cash=_num(row.get("cash_and_equivalents")),
                                    ebitda=None if None in (opinc, da) else opinc + da, sbc=sbc, module=module)
    out.update(leverage_status=lev.get("status"), leverage_risk_band=lev.get("risk_band"),
               debt_to_ebitda_after_sbc=lev.get("gross_debt_to_ebitda_after_sbc"), leverage_secondary_view_only=True)
    return out


def run(rows: List[dict], evidence: Optional[dict] = None, *, components: Optional[dict] = None,
        economic_registry: Optional[List[dict]] = None, decision_gate_done: bool = False) -> Dict[str, Any]:
    comp = components or load_components()
    engine, adapter, market, lane, cash = (comp[k] for k in ("engine", "adapter", "classifier", "lane", "cash"))
    evidence = evidence or {"schema": EVIDENCE_SCHEMA, "entities": {}}
    if evidence.get("schema") != EVIDENCE_SCHEMA or not isinstance(evidence.get("entities"), dict):
        raise IntegrationError("evidence schema mismatch")
    _strict_bool(decision_gate_done, "decision_gate_done")
    keys = [r.get("ticker") for r in rows]
    if any(not k for k in keys) or len(set(keys)) != len(keys):
        raise IntegrationError("entity keys must be present and unique")
    unknown = sorted(set(evidence["entities"]) - set(keys))
    if unknown:
        raise IntegrationError(f"evidence for unknown entities: {len(unknown)}")
    registry = economic_registry or []
    results: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = row["ticker"]
        ev = evidence["entities"].get(key) or {}
        c = adapter.derive(row, engine)
        restore_growth_guard_inputs(c, row)
        guards = []
        if MIXED_BASIS_SUFFIX in (row.get("data_quality_flags") or ""):
            if c["fcf_margin"] is not None or c["net_margin"] is not None:
                raise IntegrationError("mixed-basis row carries margin ratios")
            c["reinvestment_rate"] = None
            guards.append("MIXED_BASIS_RATIOS_SUPPRESSED")
        original = c["module"]
        br09 = classify_entity(row, original, ev.get("br09"), market)
        c["module"] = br09["final_module"]
        for name, value in br09["kpis"].items():
            c[name] = value
        score, coverage, detail, growth_flags = engine.bqs(c)
        confidence = engine.bqs_confidence(coverage, c.get("data_coverage_pct") or 0, "PRESENT",
                                           detail.get("_metric_coverage_pct", 0), detail.get("_provisional_components", []))
        ios_value, ios_detail = engine.ios(c, score, coverage)
        results[key] = dict(
            entity_key=key, module_original=original, module_final=c["module"], ios_variant=engine.ios_variant(c["module"]),
            br09=dict((k, v) for k, v in br09.items() if k != "kpis"), marketplace_kpis=br09["kpis"],
            bqs=score, bqs_coverage_pct=coverage, bqs_confidence=confidence, growth_flags=sorted(growth_flags),
            bqs_components={k: v for k, v in sorted(detail.items()) if not k.startswith("_")},
            ios=ios_value, ios_gate="CALCULABLE" if ios_value is not None else ios_detail.get("gate", "UNSPECIFIED"),
            growth_policy=ios_detail.get("growth_policy"), data_guards=guards,
            data_conflict=any(v == "CONFLICTING" for v in row.values()) or br09["kpi_conflict"] or bool(open_conflicts(ev)),
            open_data_conflicts=open_conflicts(ev),
            market_data_status=row.get("market_data_status") or "MISSING", _c=c, _row=row, _ev=ev)
    lane_v = [dict(entity_key=k, ios=r["ios"], bqs=r["bqs"]) for k, r in results.items() if r["ios"] is not None]
    lane_v.sort(key=lambda r: (-float(r["ios"]), -float(r["bqs"]), r["entity_key"]))
    for i, r in enumerate(lane_v, 1):
        results[r["entity_key"]]["lane_v_rank"] = i
    lane_inputs = []
    for key, r in results.items():
        c, row, ev = r["_c"], r["_row"], r["_ev"]
        flags_ev = ev.get("lane_flags")
        owner = cash.reported_owner_earnings(c.get("ocf"), c.get("capex"), c.get("sbc")).get("reported_owner_earnings")
        item = dict(entity_key=key, bqs=r["bqs"], owner_earnings=owner, revenue_cagr3=c.get("revenue_cagr3"),
                    fcf_cagr3=c.get("fcf_cagr3"), fcf_per_share_cagr3=c.get("fcf_per_share_cagr3"),
                    cash_conversion=c.get("cash_conversion"), share_change=c.get("share_change"),
                    growth_flags=r["growth_flags"], quality_flags=sorted((flags_ev or {}).get("quality_flags") or []),
                    cyclical_rebound_flag=_strict_bool((flags_ev or {}).get("cyclical_rebound_flag", False), "cyclical_rebound_flag"))
        a = lane.inflection_assessment(item)
        r["lane_i"] = dict(eligible=a["eligible"], high_confidence=a["high_confidence"], score=a["score"],
                           confidence=a["confidence"], reason_code=a["reason_code"], reasons=a.get("reasons", []),
                           missing=a.get("missing", []), flags=a.get("flags", []), flags_reviewed=flags_ev is not None)
        lane_inputs.append(item)
    lane_i = lane.rank_lane_i(lane_inputs)
    for i, r in enumerate(lane_i, 1):
        results[r["entity_key"]]["lane_i_rank"] = i
    queue = lane.merge_deep_dive_queue(lane_v, lane_i)
    queue_out = []
    for i, q in enumerate(queue, 1):
        r = results[q["entity_key"]]
        r["queue_rank"], r["selection_lane"] = i, q["selection_lane"]
        r["overlay"] = overlay_entity(r["_row"], r["module_final"], r["_ev"], cash)
        queue_out.append(dict(queue_rank=i, entity_key=q["entity_key"], selection_lane=q["selection_lane"]))
    for key, r in results.items():
        ev = r.pop("_ev"); r.pop("_c"); r.pop("_row")
        open_flags = sorted(x["flag_id"] for x in registry if x.get("case_id") == key and x.get("economic_case_closed") is not True)
        clearance = (ev.get("economic_clearance") or {})
        cleared = _strict_bool(clearance.get("independent", False), "economic_clearance.independent") and bool(str(clearance.get("reference", "")).strip())
        reasons = []
        if "queue_rank" not in r:
            reasons.append("NOT_IN_DEEP_DIVE_QUEUE")
        if r["ios"] is None:
            reasons.append("IOS_NOT_CALCULABLE")
        if r["market_data_status"] != "PRESENT":
            reasons.append("MARKET_DATA_NOT_PRESENT")
        if r["br09"]["classification_status"] != market.VERIFIED:
            reasons.append("BR09_PROVISIONAL")
        ov = r.get("overlay")
        if ov is not None:
            if ov["cash_quality_gate"] != "NO_ADDITIONAL_CASH_QUALITY_BLOCK":
                reasons.append("CASH_QUALITY_" + ov["cash_quality_gate"])
            if ov["commitments_gate"] != "NO_AUTOMATIC_BLOCK":
                reasons.append("COMMITMENTS_" + ov["commitments_gate"])
            elif not ov["commitment_inventory_complete"]:
                reasons.append("COMMITMENT_INVENTORY_NOT_ATTESTED")
            if not r["lane_i"]["flags_reviewed"]:
                reasons.append("QUALITY_FLAGS_NOT_REVIEWED")
        if open_flags:
            reasons.append("UNRESOLVED_ECONOMIC_CASE")
        if not cleared:
            reasons.append("INDEPENDENT_ECONOMIC_CLEARANCE_MISSING")
        unresolved = bool(reasons)
        allowed, reason = engine.can_emit_buy(False, decision_gate_done, unresolved, r["data_conflict"])
        if allowed is not False:
            raise IntegrationError("release attempted while NOT LIVE")
        hypo, hypo_reason = engine.can_emit_buy(True, True, unresolved, r["data_conflict"])
        r["decision"] = dict(buy_add_allowed=False, system_live=False, engine_reason=reason,
                             unresolved_red_flag=unresolved, unresolved_reasons=reasons, economic_flag_ids=open_flags,
                             allowed_under_hypothetical_live_state=hypo, hypothetical_reason=hypo_reason,
                             action="DECISION_GATE_ELIGIBLE_NOT_LIVE" if hypo else ("INVESTIGARE" if "queue_rank" in r else "NON FARE NULLA"))
    ordered = [results[k] for k in sorted(results)]
    counts: Dict[str, int] = {}
    for r in ordered:
        counts[r["ios_gate"]] = counts.get(r["ios_gate"], 0) + 1
    return dict(schema=OUTPUT_SCHEMA, pipeline_version=PIPELINE_VERSION, engine_version=engine.ENGINE_VERSION,
                growth_policy=engine.GROWTH_POLICY, classifier_version=market.CLASSIFIER_VERSION,
                lane_version=lane.LANE_I_VERSION, overlay_version=cash.MODULE_VERSION,
                component_sha256={k: v[1] for k, v in sorted(FROZEN_COMPONENTS.items())},
                system_live=False, rows=len(ordered), ios_gate_counts=dict(sorted(counts.items())),
                buy_add_allowed_rows=sum(r["decision"]["buy_add_allowed"] for r in ordered),
                deep_dive_queue=queue_out, lane_i_high_confidence=[r["entity_key"] for r in lane_i], results=ordered)


def _round(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 10)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> bytes:
    return (json.dumps(_round(obj), sort_keys=True, indent=1, ensure_ascii=True, allow_nan=False) + "\n").encode()


def read_candidate(raw: bytes) -> List[dict]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise IntegrationError("malformed candidate row")
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Investment OS V4.2 integrated run. Research/validation only; never LIVE.")
    p.add_argument("--candidate", required=True)
    p.add_argument("--evidence")
    p.add_argument("--registry", help="economic registry JSON with a 'records' list")
    p.add_argument("--expect-candidate-sha256")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    raw = Path(a.candidate).read_bytes()
    if a.expect_candidate_sha256 and sha256_bytes(raw) != a.expect_candidate_sha256:
        raise IntegrationError("candidate hash mismatch")
    ev_raw = Path(a.evidence).read_bytes() if a.evidence else None
    reg_raw = Path(a.registry).read_bytes() if a.registry else None
    result = run(read_candidate(raw), json.loads(ev_raw) if ev_raw else None,
                 economic_registry=json.loads(reg_raw)["records"] if reg_raw else None)
    result["inputs"] = dict(candidate_sha256=sha256_bytes(raw), evidence_sha256=sha256_bytes(ev_raw) if ev_raw else None,
                            registry_sha256=sha256_bytes(reg_raw) if reg_raw else None)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(result)
    (out / "integrated_run.json").write_bytes(payload)
    summary = {k: result[k] for k in ("schema", "pipeline_version", "engine_version", "component_sha256", "system_live",
                                     "rows", "ios_gate_counts", "buy_add_allowed_rows", "inputs")}
    summary["queue_size"] = len(result["deep_dive_queue"])
    summary["integrated_run_sha256"] = sha256_bytes(payload)
    (out / "integrated_summary.json").write_bytes(canonical_json(summary))
    print("INTEGRATED_RUN=" + json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
